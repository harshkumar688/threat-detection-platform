"""
Live Feed Handler

Captures frames from a webcam (or video file) using OpenCV, encodes them
as JPEG, and sends them as base64 over a WebSocket alongside structured
detection metadata.

Detection is optional — if the YOLO libraries (ultralytics + torch) are not
available in the current Python environment, the handler still streams clean
video frames with no detection overlay. This makes the live feed resilient:
it always works even when the ML libraries live in a separate virtual env.

Message format sent to the browser (JSON):
{
    "type":          "frame",
    "frame_b64":     "<base64 JPEG string>",   // data:image/jpeg;base64,...
    "frame_number":  1234,
    "fps":           8.3,
    "detections":    [
        {
            "class_name":  "knife",
            "confidence":  0.82,
            "is_weapon":   true,
            "bbox":        {"x1": 0.2, "y1": 0.1, "x2": 0.5, "y2": 0.6},
            "track_id":    null
        }
    ],
    "has_weapons":   true,
    "risk_level":    "HIGH",
    "risk_score":    72
}
"""

import asyncio
import base64
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# One shared thread-pool for all camera I/O + inference tasks.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="feed")

# Try to import the detection pipeline — graceful no-op if not available.
_detector_available = False
try:
    import sys
    import os
    # Look for the detection service next to the backend folder.
    _detection_src = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "detection", "src")
    )
    if _detection_src not in sys.path:
        sys.path.insert(0, os.path.dirname(_detection_src))
    from detection.src.config import DetectionConfig  # noqa: E402 F401
    from detection.src.inference.detector import YOLODetector  # noqa: E402 F401
    from detection.src.inference.visualizer import draw_detections  # noqa: E402 F401
    from detection.src.models import FrameResult  # noqa: E402 F401
    from detection.src.scoring.scorer import RiskScorer  # noqa: E402 F401

    _detector_available = True
    logger.info("Detection libraries available — live feed will include YOLO inference")
except Exception as e:
    logger.info("Detection libraries not available in this env (%s) — streaming frames only", e)


class FeedHandler:
    """
    Captures and optionally annotates a camera feed, yielding frame payloads
    suitable for WebSocket streaming to the dashboard.
    """

    def __init__(
        self,
        source: int | str = 0,
        fps: int = 8,
        jpeg_quality: int = 70,
        confidence_threshold: float = 0.4,
        model_path: str = "yolov8n.pt",
    ):
        """
        Args:
            source: OpenCV capture source — integer for webcam index, string
                    for video file path or RTSP URL.
            fps: Target frames per second to stream (limits CPU load).
            jpeg_quality: JPEG encode quality 1-95. Lower = smaller payload.
            confidence_threshold: Minimum detection confidence.
            model_path: YOLO model path/name (only used if detector available).
        """
        self.source = source
        self.fps = fps
        self.jpeg_quality = jpeg_quality
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path

        self._cap: Optional[cv2.VideoCapture] = None
        self._detector: Optional[Any] = None
        self._scorer: Optional[Any] = None
        self._running = False

    def _initialize(self) -> None:
        """Called once from the worker thread."""
        self._cap = cv2.VideoCapture(self.source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera source: {self.source!r}")

        if _detector_available:
            try:
                from detection.src.config import DetectionConfig
                from detection.src.inference.detector import YOLODetector
                from detection.src.scoring.scorer import RiskScorer

                config = DetectionConfig(
                    model_path=self.model_path,
                    device="cpu",
                    confidence_threshold=self.confidence_threshold,
                )
                self._detector = YOLODetector(config)
                self._detector.initialize()
                self._scorer = RiskScorer()
                logger.info("Detector initialized for live feed (model=%s)", self.model_path)
            except Exception as e:
                logger.warning("Detector init failed: %s — streaming without detection", e)
                self._detector = None

    def _release(self) -> None:
        if self._cap:
            self._cap.release()

    def _read_and_process_frame(self, frame_number: int) -> Optional[Dict]:
        """
        Reads one frame, runs detection if available, encodes to JPEG base64.
        Returns the JSON-serializable frame payload, or None on read error.
        """
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None

        detections_payload: List[Dict] = []
        has_weapons = False
        risk_level = "LOW"
        risk_score = 0

        if self._detector is not None:
            try:
                from detection.src.inference.visualizer import draw_detections

                result = self._detector.detect_frame(frame, frame_number=frame_number)
                detections_payload = [
                    {
                        "class_name": d.class_name,
                        "confidence": round(d.confidence, 3),
                        "is_weapon": d.is_weapon,
                        "bbox": {
                            "x1": round(d.bbox.x1, 4),
                            "y1": round(d.bbox.y1, 4),
                            "x2": round(d.bbox.x2, 4),
                            "y2": round(d.bbox.y2, 4),
                        },
                        "track_id": None,
                    }
                    for d in result.detections
                ]
                has_weapons = result.has_weapons

                if has_weapons and self._scorer:
                    weapons = result.weapon_detections
                    top = max(weapons, key=lambda d: d.confidence)
                    scored = self._scorer.score(
                        weapon_class=top.class_name,
                        avg_confidence=top.confidence,
                        frames_confirmed=1,
                        weapon_count=len(weapons),
                    )
                    risk_level = scored.risk_level.value
                    risk_score = round(scored.risk_score)

                # Draw bounding boxes onto the frame before encoding.
                draw_detections(frame, result, bbox_thickness=2, font_scale=0.5)

            except Exception as e:
                logger.debug("Detection error on frame %d: %s", frame_number, e)

        # Encode frame as JPEG.
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        success, buf = cv2.imencode(".jpg", frame, encode_params)
        if not success:
            return None

        b64 = base64.b64encode(buf.tobytes()).decode("ascii")

        return {
            "type": "frame",
            "frame_b64": b64,
            "frame_number": frame_number,
            "detections": detections_payload,
            "has_weapons": has_weapons,
            "risk_level": risk_level,
            "risk_score": risk_score,
        }

    def run_in_thread(self, on_frame, stop_event) -> None:
        """
        Main capture loop — runs in a worker thread.

        Args:
            on_frame: Sync callable(payload: dict) called per frame.
            stop_event: threading.Event — set to stop the loop.
        """
        import threading

        self._initialize()
        frame_number = 0
        interval = 1.0 / max(1, self.fps)

        try:
            while not stop_event.is_set():
                t0 = time.perf_counter()
                frame_number += 1

                payload = self._read_and_process_frame(frame_number)
                if payload is None:
                    logger.info("Feed source ended or read failed at frame %d", frame_number)
                    break

                on_frame(payload)

                elapsed = time.perf_counter() - t0
                sleep = interval - elapsed
                if sleep > 0:
                    time.sleep(sleep)
        finally:
            self._release()
