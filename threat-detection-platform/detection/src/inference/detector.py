"""
YOLO Detector

Core inference engine. Receives frames, runs YOLO model, and returns
structured Detection objects.

Responsibilities:
- Run inference on single frames (numpy arrays)
- Apply confidence threshold and NMS
- Convert raw model output to Detection dataclass
- Track inference timing

Does NOT handle:
- Video I/O (that's the FrameSource's job)
- Tracking (that's a separate module)
- Scoring (that's a separate module)
"""

import time
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

from ..config import DetectionConfig
from ..logger import get_logger
from ..models import BoundingBox, Detection, FrameResult, is_weapon_class
from .model_loader import ModelLoader, ModelLoadError

logger = get_logger(__name__)


class DetectionError(Exception):
    """Raised when inference fails."""
    pass


class YOLODetector:
    """
    YOLO-based object detector.

    Usage:
        config = DetectionConfig()
        detector = YOLODetector(config)
        detector.initialize()

        # Single frame inference
        result = detector.detect_frame(frame, frame_number=1)
        for det in result.detections:
            print(f"{det.class_name}: {det.confidence:.2f}")
    """

    def __init__(self, config: DetectionConfig):
        """
        Initialize detector with configuration.

        Args:
            config: Detection configuration object.
        """
        self.config = config
        self._loader: Optional[ModelLoader] = None
        self._frame_count = 0

    def initialize(self) -> None:
        """
        Load the model and prepare for inference.

        Must be called before detect_frame().

        Raises:
            ModelLoadError: If model cannot be loaded.
        """
        self._loader = ModelLoader(
            model_path=self.config.model_path,
            device=self.config.device,
            input_size=self.config.input_size,
        )
        self._loader.load()
        self._frame_count = 0

        logger.info(
            "detector_initialized",
            model=self.config.model_path,
            confidence_threshold=self.config.confidence_threshold,
            nms_iou_threshold=self.config.nms_iou_threshold,
            input_size=self.config.input_size,
        )

    @property
    def is_ready(self) -> bool:
        """Check if detector is initialized and ready for inference."""
        return self._loader is not None and self._loader.is_loaded

    @property
    def class_names(self) -> List[str]:
        """Get the class names from the loaded model."""
        if self._loader is None:
            return []
        return self._loader.class_list

    def detect_frame(
        self,
        frame: np.ndarray,
        frame_number: Optional[int] = None,
        source: str = "",
    ) -> FrameResult:
        """
        Run detection on a single frame.

        Args:
            frame: BGR image as numpy array (H, W, 3), uint8.
            frame_number: Optional frame number. Auto-increments if not provided.
            source: Source identifier (file path, camera ID, etc.)

        Returns:
            FrameResult with all detections for this frame.

        Raises:
            DetectionError: If inference fails.
            ModelLoadError: If model is not loaded.
        """
        if not self.is_ready:
            raise ModelLoadError("Detector not initialized. Call initialize() first.")

        if frame is None or frame.size == 0:
            raise DetectionError("Invalid frame: frame is None or empty.")

        if len(frame.shape) != 3 or frame.shape[2] != 3:
            raise DetectionError(
                f"Invalid frame shape: expected (H, W, 3), got {frame.shape}"
            )

        # Auto-increment frame count
        if frame_number is None:
            self._frame_count += 1
            frame_number = self._frame_count
        else:
            self._frame_count = frame_number

        frame_height, frame_width = frame.shape[:2]

        # Run inference with timing
        start_time = time.perf_counter()

        try:
            results = self._loader.model.predict(
                source=frame,
                imgsz=self.config.input_size,
                conf=self.config.confidence_threshold,
                iou=self.config.nms_iou_threshold,
                verbose=False,
                classes=self._get_target_class_ids(),
            )
        except Exception as e:
            raise DetectionError(f"Inference failed on frame {frame_number}: {e}") from e

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Parse results
        detections = self._parse_results(results, frame_width, frame_height)

        # Apply target class filter (by name, if configured)
        if self.config.target_classes:
            target_set = {name.lower() for name in self.config.target_classes}
            detections = [d for d in detections if d.class_name.lower() in target_set]

        result = FrameResult(
            frame_number=frame_number,
            timestamp=datetime.now(timezone.utc),
            detections=detections,
            frame_width=frame_width,
            frame_height=frame_height,
            inference_time_ms=inference_time_ms,
            source=source,
        )

        if detections:
            logger.debug(
                "frame_detections",
                frame=frame_number,
                count=len(detections),
                weapons=len(result.weapon_detections),
                inference_ms=round(inference_time_ms, 1),
            )

        return result

    def _parse_results(
        self,
        results,
        frame_width: int,
        frame_height: int,
    ) -> List[Detection]:
        """
        Parse YOLO results into Detection objects.

        Args:
            results: Ultralytics Results object.
            frame_width: Original frame width for normalization.
            frame_height: Original frame height for normalization.

        Returns:
            List of Detection objects.
        """
        detections = []

        if not results or len(results) == 0:
            return detections

        result = results[0]  # Single image, take first result

        if result.boxes is None or len(result.boxes) == 0:
            return detections

        boxes = result.boxes

        for i in range(len(boxes)):
            # Get box coordinates (xyxy format, pixel coords)
            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()

            # Normalize to 0-1 range
            bbox = BoundingBox(
                x1=float(x1 / frame_width),
                y1=float(y1 / frame_height),
                x2=float(x2 / frame_width),
                y2=float(y2 / frame_height),
            )

            # Get class info
            class_id = int(boxes.cls[i].cpu().numpy())
            confidence = float(boxes.conf[i].cpu().numpy())
            class_name = self._loader.class_names.get(class_id, f"class_{class_id}")

            detection = Detection(
                class_id=class_id,
                class_name=class_name,
                confidence=confidence,
                bbox=bbox,
                is_weapon=is_weapon_class(class_name),
            )

            detections.append(detection)

        return detections

    def _get_target_class_ids(self) -> Optional[List[int]]:
        """
        Get target class IDs for YOLO filtering.

        Returns None if no filter is set (detect all classes).
        """
        if not self.config.target_classes or not self._loader:
            return None

        target_set = {name.lower() for name in self.config.target_classes}
        class_ids = []

        for class_id, class_name in self._loader.class_names.items():
            if class_name.lower() in target_set:
                class_ids.append(class_id)

        return class_ids if class_ids else None

    def get_info(self) -> dict:
        """Get detector status information."""
        return {
            "is_ready": self.is_ready,
            "frames_processed": self._frame_count,
            "config": {
                "model_path": self.config.model_path,
                "device": self.config.device,
                "input_size": self.config.input_size,
                "confidence_threshold": self.config.confidence_threshold,
                "nms_iou_threshold": self.config.nms_iou_threshold,
                "target_classes": self.config.target_classes,
            },
            "model_info": self._loader.get_model_info() if self._loader else None,
        }
