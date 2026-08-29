"""
Detection Engine

High-level public API that orchestrates:
- Model loading
- Frame source management
- Inference execution
- Visualization

This is the main entry point for external modules to use.
"""

from pathlib import Path
from typing import Generator, Optional

import cv2
import numpy as np

from ..config import DetectionConfig
from ..logger import get_logger
from ..models import FrameResult
from .detector import YOLODetector
from .frame_source import FrameSource, FrameSourceError, is_image_file, is_video_file
from .model_loader import ModelLoadError
from .visualizer import draw_detections, draw_frame_info

logger = get_logger(__name__)


class DetectionEngine:
    """
    High-level detection engine.

    Provides a simple interface for running weapon/person detection on:
    - Single images
    - Video files
    - Webcam streams

    Usage:
        from detection.src.inference.engine import DetectionEngine
        from detection.src.config import DetectionConfig

        config = DetectionConfig(model_path="yolov8n.pt")
        engine = DetectionEngine(config)
        engine.start()

        # Detect on image
        result = engine.detect_image("path/to/image.jpg")

        # Detect on video (generator)
        for result, annotated_frame in engine.detect_video("path/to/video.mp4"):
            print(f"Frame {result.frame_number}: {result.detection_count} detections")

        engine.stop()
    """

    def __init__(self, config: Optional[DetectionConfig] = None):
        """
        Initialize engine with configuration.

        Args:
            config: Detection configuration. Uses defaults if not provided.
        """
        self.config = config or DetectionConfig()
        self._detector = YOLODetector(self.config)
        self._is_running = False

    def start(self) -> None:
        """
        Start the detection engine (load model).

        Raises:
            ModelLoadError: If model loading fails.
        """
        logger.info("engine_starting", model=self.config.model_path)
        self._detector.initialize()
        self._is_running = True
        logger.info("engine_started")

    def stop(self) -> None:
        """Stop the detection engine and release resources."""
        self._is_running = False
        logger.info("engine_stopped")

    @property
    def is_running(self) -> bool:
        """Check if engine is running and ready."""
        return self._is_running and self._detector.is_ready

    def detect_image(self, image_path: str) -> FrameResult:
        """
        Run detection on a single image file.

        Args:
            image_path: Path to image file (JPEG, PNG, etc.)

        Returns:
            FrameResult with detections.

        Raises:
            FrameSourceError: If image cannot be read.
            ModelLoadError: If model is not loaded.
        """
        self._ensure_running()

        source = FrameSource.from_image(image_path)
        for frame, frame_num in source.frames():
            result = self._detector.detect_frame(
                frame, frame_number=frame_num, source=image_path
            )
            return result

        raise FrameSourceError(f"No frames read from image: {image_path}")

    def detect_frame_array(self, frame: np.ndarray, source: str = "") -> FrameResult:
        """
        Run detection on a raw numpy frame.

        Args:
            frame: BGR image as numpy array (H, W, 3).
            source: Optional source identifier.

        Returns:
            FrameResult with detections.
        """
        self._ensure_running()
        return self._detector.detect_frame(frame, source=source)

    def detect_video(
        self,
        video_path: str,
        max_fps: Optional[int] = None,
        annotate: Optional[bool] = None,
    ) -> Generator[tuple, None, None]:
        """
        Run detection on a video file, yielding results frame by frame.

        Args:
            video_path: Path to video file.
            max_fps: Override max FPS (uses config default if None).
            annotate: Whether to draw bounding boxes (uses config default if None).

        Yields:
            Tuple of (FrameResult, annotated_frame: np.ndarray or None)

        Raises:
            FrameSourceError: If video cannot be opened.
        """
        self._ensure_running()

        fps = max_fps or self.config.max_fps
        do_annotate = annotate if annotate is not None else self.config.draw_bboxes

        source = FrameSource.from_video(video_path, max_fps=fps)
        try:
            for frame, frame_num in source.frames():
                result = self._detector.detect_frame(
                    frame, frame_number=frame_num, source=video_path
                )

                annotated = None
                if do_annotate:
                    annotated = frame.copy()
                    draw_detections(
                        annotated, result,
                        bbox_thickness=self.config.bbox_thickness,
                        font_scale=self.config.font_scale,
                    )
                    draw_frame_info(annotated, result)

                yield result, annotated
        finally:
            source.release()

    def detect_webcam(
        self,
        device_index: Optional[int] = None,
        max_fps: Optional[int] = None,
        annotate: Optional[bool] = None,
    ) -> Generator[tuple, None, None]:
        """
        Run detection on webcam feed, yielding results frame by frame.

        Args:
            device_index: Camera device index (uses config default if None).
            max_fps: Override max FPS.
            annotate: Whether to draw bounding boxes.

        Yields:
            Tuple of (FrameResult, annotated_frame: np.ndarray or None)
        """
        self._ensure_running()

        device = device_index if device_index is not None else self.config.webcam_index
        fps = max_fps or self.config.max_fps
        do_annotate = annotate if annotate is not None else self.config.draw_bboxes

        source = FrameSource.from_webcam(device_index=device, max_fps=fps)
        try:
            for frame, frame_num in source.frames():
                result = self._detector.detect_frame(
                    frame,
                    frame_number=frame_num,
                    source=f"webcam:{device}",
                )

                annotated = None
                if do_annotate:
                    annotated = frame.copy()
                    draw_detections(
                        annotated, result,
                        bbox_thickness=self.config.bbox_thickness,
                        font_scale=self.config.font_scale,
                    )
                    draw_frame_info(annotated, result)

                yield result, annotated
        finally:
            source.release()

    def detect_and_display(
        self,
        source_path: str,
        window_name: str = "Threat Detection",
    ) -> None:
        """
        Run detection and display results in an OpenCV window.

        Useful for development/debugging. Press 'q' to quit.

        Args:
            source_path: Image, video path, or "webcam" / "webcam:0"
        """
        self._ensure_running()

        # Determine source type
        if source_path.startswith("webcam"):
            parts = source_path.split(":")
            device = int(parts[1]) if len(parts) > 1 else self.config.webcam_index
            gen = self.detect_webcam(device_index=device, annotate=True)
        elif is_image_file(source_path):
            result = self.detect_image(source_path)
            frame = cv2.imread(source_path)
            draw_detections(frame, result, self.config.bbox_thickness, self.config.font_scale)
            draw_frame_info(frame, result)
            cv2.imshow(window_name, frame)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            return
        elif is_video_file(source_path):
            gen = self.detect_video(source_path, annotate=True)
        else:
            raise FrameSourceError(f"Cannot determine source type for: {source_path}")

        try:
            for result, annotated_frame in gen:
                if annotated_frame is not None:
                    cv2.imshow(window_name, annotated_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        logger.info("display_quit_by_user")
                        break
        finally:
            cv2.destroyAllWindows()

    def _ensure_running(self) -> None:
        """Ensure engine is started."""
        if not self.is_running:
            raise ModelLoadError(
                "Detection engine is not running. Call engine.start() first."
            )

    def get_info(self) -> dict:
        """Get engine status and configuration."""
        return {
            "is_running": self.is_running,
            "detector": self._detector.get_info(),
        }
