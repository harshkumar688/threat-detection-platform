"""
Live Feed Streams Router

WebSocket endpoints for real-time camera feed + detection streaming.

Endpoints:
  WS  /streams/feed/{camera_id}
      Connect to receive a live stream of annotated JPEG frames and
      detection metadata for the specified camera. Requires a valid JWT
      passed as a query parameter:
        ws://localhost:8000/api/v1/streams/feed/{cam_id}?token=<access_token>

Frame message format (JSON, sent server → client):
  {
    "type":         "frame",
    "frame_b64":    "<base64 JPEG>",
    "frame_number": 42,
    "fps":          8.0,
    "detections":   [{class_name, confidence, is_weapon, bbox, track_id}, ...],
    "has_weapons":  false,
    "risk_level":   "LOW",
    "risk_score":   0
  }

Control messages (JSON, sent server → client):
  { "type": "connected", "camera_id": "...", "source": "webcam:0" }
  { "type": "error", "message": "..." }
  { "type": "ended" }

The camera feed source is resolved from the registered camera record
(stream_url field). If the camera_id is "webcam" or not found as a
registered camera, the default webcam (device 0) is used.
"""

import asyncio
import logging
import threading
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streams", tags=["Live Streams"])


def _resolve_source(camera_id: str) -> int | str:
    """
    Resolve a camera_id to an OpenCV capture source.

    For the prototype:
    - "webcam" or "webcam:N" -> integer device index N (default 0)
    - A registered camera's stream_url is returned as-is if it looks like
      an RTSP URL, otherwise webcam 0 is used as a safe fallback.
    """
    if camera_id.lower().startswith("webcam"):
        parts = camera_id.split(":")
        try:
            return int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            return 0

    # Try to look up a registered camera's stream_url.
    try:
        from app.api.v1.cameras import _camera_service
        import asyncio
        from uuid import UUID

        async def _get():
            try:
                from app.cameras.exceptions import CameraNotFoundError
                cam = await _camera_service.get_camera(UUID(camera_id))
                return cam.stream_url
            except Exception:
                return None

        url = asyncio.run(_get())
        if url and (url.startswith("rtsp://") or url.startswith("http://")):
            return url
        if url and url.startswith("webcam://"):
            try:
                return int(url.split("://")[1])
            except Exception:
                return 0
    except Exception:
        pass

    return 0  # Default to webcam 0


@router.websocket("/feed/{camera_id}")
async def ws_feed(
    websocket: WebSocket,
    camera_id: str,
    token: Optional[str] = Query(default=None, description="JWT access token"),
    fps: int = Query(default=8, ge=1, le=30),
    quality: int = Query(default=70, ge=10, le=95),
    conf: float = Query(default=0.4, ge=0.1, le=0.95),
    model: str = Query(default="yolov8n.pt"),
):
    """
    WebSocket: stream live annotated frames for a camera.

    Authentication: pass JWT as ?token=<access_token> query param.
    Fires 4008 (Policy Violation) if the token is missing or invalid.
    """
    # --- Authentication ---
    if not token:
        await websocket.close(code=4008, reason="Authentication required")
        return

    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        await websocket.close(code=4008, reason="Invalid or expired token")
        return

    user_id = payload.get("sub", "unknown")

    # --- Connect ---
    await manager.connect(websocket, key=camera_id)

    source = _resolve_source(camera_id)
    logger.info("ws_feed started camera=%s source=%r user=%s fps=%d", camera_id, source, user_id, fps)

    await manager.send_json(
        {"type": "connected", "camera_id": camera_id, "source": str(source)},
        websocket,
    )

    # --- Start capture in a background thread ---
    from app.websocket.feed_handler import FeedHandler

    handler = FeedHandler(
        source=source,
        fps=fps,
        jpeg_quality=quality,
        confidence_threshold=conf,
        model_path=model,
    )

    stop_event = threading.Event()
    frame_queue: asyncio.Queue = asyncio.Queue(maxsize=4)
    loop = asyncio.get_event_loop()

    def on_frame(payload: dict):
        """Called from the worker thread; bridges to the async queue."""
        try:
            # put_nowait drops the frame if the queue is full rather than
            # blocking the capture thread — keeps the stream real-time.
            loop.call_soon_threadsafe(frame_queue.put_nowait, payload)
        except Exception:
            pass

    capture_thread = threading.Thread(
        target=handler.run_in_thread,
        args=(on_frame, stop_event),
        daemon=True,
        name=f"feed-{camera_id}",
    )
    capture_thread.start()

    # --- Stream loop ---
    try:
        while True:
            # Wait for the next frame or a client message (ping/close).
            frame_task = asyncio.create_task(frame_queue.get())
            receive_task = asyncio.create_task(websocket.receive_text())

            done, pending = await asyncio.wait(
                {frame_task, receive_task},
                timeout=5.0,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for t in pending:
                t.cancel()

            if not done:
                # Timeout — check if client is still alive.
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue

            if receive_task in done:
                # Client sent a message (could be a close frame).
                try:
                    msg = receive_task.result()
                    if msg == "stop":
                        break
                except WebSocketDisconnect:
                    break
                except Exception:
                    break

            if frame_task in done:
                frame_payload = frame_task.result()
                sent = await manager.send_json(frame_payload, websocket)
                if not sent:
                    break

    except WebSocketDisconnect:
        logger.info("ws_feed disconnected camera=%s user=%s", camera_id, user_id)
    except Exception as e:
        logger.exception("ws_feed error camera=%s: %s", camera_id, e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        stop_event.set()
        manager.disconnect(websocket, key=camera_id)
        capture_thread.join(timeout=3.0)
        logger.info("ws_feed closed camera=%s", camera_id)
