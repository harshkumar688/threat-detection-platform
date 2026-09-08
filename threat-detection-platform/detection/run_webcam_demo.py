"""
Live Webcam Detection Demo

Runs the real detection pipeline against the laptop webcam. Prints every
detection to the console, and (in --api mode) pushes confirmed weapon
detections to the running backend as real incidents, so they appear in
the dashboard (Incidents page, Live Monitoring, Alerts).

Pipeline per frame:
    webcam frame -> YOLODetector (real inference)
                 -> console print (class + confidence)
                 -> if a weapon class is confirmed for N consecutive frames,
                    RiskScorer computes a 0-100 score, and in --api mode a
                    real incident is POSTed to the backend.

Model note: yolov8n.pt is COCO-trained (general purpose). COCO includes
"knife" and "scissors". By default only "knife" counts as a weapon (matches
the platform's WEAPON_CLASSES). Use --weapon-classes to add others you can
test with on hand, e.g.:

    --weapon-classes knife,scissors,"baseball bat"

Usage examples:
    # Console + video window only (no backend):
    C:\\td-venv\\Scripts\\python.exe run_webcam_demo.py

    # Push confirmed detections to the dashboard:
    C:\\td-venv\\Scripts\\python.exe run_webcam_demo.py --api --weapon-classes knife,scissors,"baseball bat"

Press Ctrl+C here (or 'q' in the window) to stop.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import cv2

from src.config import DetectionConfig
from src.inference.detector import YOLODetector
from src.inference.frame_source import FrameSource, FrameSourceError
from src.inference.model_loader import ModelLoadError
from src.inference.visualizer import draw_detections, draw_frame_info
from src.scoring.scorer import RiskScorer


# ---------------------------------------------------------------------------
# Backend bridge (only used in --api mode)
# ---------------------------------------------------------------------------

class BackendClient:
    """
    Thin client that logs into the backend, ensures a camera exists, and
    creates incidents. Uses the real public API — nothing here bypasses
    the backend's own validation or auth.
    """

    def __init__(self, base_url: str, email: str, password: str, camera_name: str):
        import requests  # local import so non-api mode has no hard dependency

        self._requests = requests
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.camera_name = camera_name
        self.token = None
        self.camera_id = None

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def login(self):
        resp = self._requests.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"email": self.email, "password": self.password},
            timeout=10,
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        print(f"[api] Logged in to backend as {self.email}")

    def ensure_camera(self):
        # Reuse an existing camera with the same name if present.
        resp = self._requests.get(f"{self.base_url}/api/v1/cameras/", headers=self._headers(), timeout=10)
        resp.raise_for_status()
        for cam in resp.json():
            if cam["name"] == self.camera_name:
                self.camera_id = cam["id"]
                print(f"[api] Reusing existing camera '{self.camera_name}' ({self.camera_id})")
                return

        resp = self._requests.post(
            f"{self.base_url}/api/v1/cameras/",
            headers=self._headers(),
            json={"name": self.camera_name, "stream_url": "webcam://0", "stream_type": "usb"},
            timeout=10,
        )
        resp.raise_for_status()
        self.camera_id = resp.json()["id"]
        print(f"[api] Registered camera '{self.camera_name}' ({self.camera_id})")

    def create_incident(self, threat_type: str, risk_level: str, description: str):
        resp = self._requests.post(
            f"{self.base_url}/api/v1/incidents/",
            headers=self._headers(),
            json={
                "camera_id": self.camera_id,
                "threat_type": threat_type,
                "risk_level": risk_level,
                "description": description,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Live webcam detection demo")
    parser.add_argument("--device", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold (default: 0.4)")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Model path/name")
    parser.add_argument("--fps", type=int, default=8, help="Max processing FPS (default: 8)")
    parser.add_argument("--no-window", action="store_true", help="Console only, no video window")
    parser.add_argument(
        "--weapon-classes",
        type=str,
        default="",
        help=(
            "Comma-separated class names to treat as weapons. If omitted, the "
            "platform default set from src.models.WEAPON_CLASSES is used "
            "(gun/pistol/handgun/rifle/firearm/weapon/knife)."
        ),
    )
    parser.add_argument("--confirm-frames", type=int, default=5,
                        help="Consecutive frames a weapon must be seen before an incident is raised (default: 5)")
    # --- API mode ---
    parser.add_argument("--api", action="store_true", help="Push confirmed detections to the backend dashboard")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--api-email", type=str, default="admin@threatplatform.local")
    parser.add_argument("--api-password", type=str, default="admin123")
    parser.add_argument("--camera-name", type=str, default="Laptop Webcam")
    parser.add_argument("--cooldown", type=float, default=15.0,
                        help="Seconds to wait before raising another incident for the same weapon (default: 15)")
    args = parser.parse_args()

    from src.models import WEAPON_CLASSES as PLATFORM_WEAPON_CLASSES

    if args.weapon_classes.strip():
        weapon_classes = {c.strip().lower() for c in args.weapon_classes.split(",") if c.strip()}
    else:
        # Use the platform's configured weapon-class set as the source of truth.
        weapon_classes = set(PLATFORM_WEAPON_CLASSES)

    config = DetectionConfig(
        model_path=args.model,
        device="cpu",
        confidence_threshold=args.conf,
        max_fps=args.fps,
        draw_bboxes=True,
    )

    print("=" * 70)
    print(f"Loading model: {config.model_path} (cpu, conf>={config.confidence_threshold}) ...")
    detector = YOLODetector(config)
    try:
        detector.initialize()
    except ModelLoadError as e:
        print(f"Failed to load model: {e}")
        sys.exit(1)
    print(f"Model loaded. Weapon classes for this run: {sorted(weapon_classes)}")

    scorer = RiskScorer()

    backend = None
    if args.api:
        try:
            backend = BackendClient(args.api_url, args.api_email, args.api_password, args.camera_name)
            backend.login()
            backend.ensure_camera()
        except Exception as e:
            print(f"[api] Backend connection failed: {e}")
            print("[api] Continuing in console-only mode.")
            backend = None

    try:
        source = FrameSource.from_webcam(device_index=args.device, max_fps=args.fps)
    except FrameSourceError as e:
        print(f"Webcam error: {e}")
        sys.exit(1)

    print(f"Webcam {args.device} open at {source.resolution[0]}x{source.resolution[1]}.")
    print("Show objects to the camera. Press Ctrl+C here (or 'q' in the window) to stop.")
    print("=" * 70)

    show_window = not args.no_window
    last_key = None
    consecutive_weapon_frames = 0
    last_incident_time = 0.0

    def is_weapon(class_name: str) -> bool:
        return class_name.lower() in weapon_classes

    try:
        for frame, frame_num in source.frames():
            result = detector.detect_frame(frame, frame_number=frame_num, source=f"webcam:{args.device}")

            # Treat configured classes as weapons for this run.
            weapons = [d for d in result.detections if is_weapon(d.class_name)]

            if result.detections:
                parts = [f"{d.class_name}({d.confidence:.2f})" for d in result.detections]
                summary = f"[frame {frame_num}] " + ", ".join(parts)
            else:
                summary = f"[frame {frame_num}] nothing detected"

            key = " ".join(sorted(d.class_name for d in result.detections))
            if key != last_key:
                print(summary)
                last_key = key

            if weapons:
                consecutive_weapon_frames += 1
                top = max(weapons, key=lambda d: d.confidence)
                risk = scorer.score(
                    weapon_class=top.class_name,
                    avg_confidence=top.confidence,
                    frames_confirmed=consecutive_weapon_frames,
                    weapon_count=len(weapons),
                )
                print(
                    f"    >>> WEAPON: {top.class_name} conf={top.confidence:.2f} | "
                    f"RISK {risk.risk_score:.0f}/100 [{risk.risk_level.value}] "
                    f"| confirmed {consecutive_weapon_frames}/{args.confirm_frames} frames"
                )

                now = time.time()
                if (
                    backend is not None
                    and consecutive_weapon_frames >= args.confirm_frames
                    and (now - last_incident_time) >= args.cooldown
                ):
                    try:
                        incident = backend.create_incident(
                            threat_type=top.class_name,
                            risk_level=risk.risk_level.value,
                            description=(
                                f"Live webcam detection: {top.class_name} "
                                f"(conf {top.confidence:.2f}, risk {risk.risk_score:.0f}/100)"
                            ),
                        )
                        last_incident_time = now
                        print(f"    *** INCIDENT CREATED in dashboard: #{incident.get('incident_number')} "
                              f"id={incident.get('id')} — check the Incidents page ***")
                    except Exception as e:
                        print(f"    [api] Failed to create incident: {e}")
            else:
                consecutive_weapon_frames = 0

            if show_window:
                annotated = frame.copy()
                draw_detections(annotated, result, config.bbox_thickness, config.font_scale)
                draw_frame_info(annotated, result)
                cv2.imshow("Threat Detection - live webcam", annotated)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    print("Quit requested from window.")
                    break
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).")
    finally:
        source.release()
        if show_window:
            cv2.destroyAllWindows()

    print("Demo stopped.")


if __name__ == "__main__":
    main()
