"""
Frame Source

Unified interface for reading frames from different sources:
- Image files (JPEG, PNG)
- Video files (MP4, AVI, MKV)
- Webcam / RTSP streams

Handles:
- Source validation
- Frame reading with error handling
- FPS limiting
- Resource cleanup
"""

import time
from pathlib import Path
from typing import Generator, Optional, Tuple

import cv2
import numpy as np

from ..logger import get_logger

logger = get_logger(__name__)


class FrameSourceError(Exception):
    """Raised when frame source cannot be opened or read."""
    pass


# Supported file extensions
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"})


def is_image_file(path: str) -> bool:
    """Check if path points to a supported image file."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def is_video_file(path: str) -> bool:
    """Check if path points to a supported video file."""
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


class FrameSource:
    """
    Unified frame source for images, videos, and webcams.

    Usage:
        # Image
        source = FrameSource.from_image("path/to/image.jpg")
        for frame, metadata in source.frames():
            process(frame)

        # Video
        source = FrameSource.from_video("path/to/video.mp4")
        for frame, metadata in source.frames():
            process(frame)

        # Webcam
        source = FrameSource.from_webcam(device_index=0)
        for frame, metadata in source.frames():
            process(frame)
    """

    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._source_path: str = ""
        self._source_type: str = ""  # "image", "video", "webcam"
        self._total_frames: int = 0
        self._fps: float = 30.0
        self._frame_width: int = 0
        self._frame_height: int = 0
        self._max_fps: int = 30

    @classmethod
    def from_image(cls, image_path: str) -> "FrameSource":
        """
        Create frame source from an image file.

        Args:
            image_path: Path to image file.

        Raises:
            FrameSourceError: If file doesn't exist or can't be read.
        """
        source = cls()
        path = Path(image_path)

        if not path.exists():
            raise FrameSourceError(f"Image file not found: {image_path}")

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise FrameSourceError(
                f"Unsupported image format: {path.suffix}. "
                f"Supported: {', '.join(sorted(IMAGE_EXTENSIONS))}"
            )

        # Test read
        frame = cv2.imread(str(path))
        if frame is None:
            raise FrameSourceError(f"Failed to read image: {image_path}")

        source._source_path = str(path)
        source._source_type = "image"
        source._total_frames = 1
        source._frame_height, source._frame_width = frame.shape[:2]
        source._fps = 1.0

        logger.info(
            "frame_source_opened",
            type="image",
            path=str(path),
            resolution=f"{source._frame_width}x{source._frame_height}",
        )

        return source

    @classmethod
    def from_video(cls, video_path: str, max_fps: int = 30) -> "FrameSource":
        """
        Create frame source from a video file.

        Args:
            video_path: Path to video file.
            max_fps: Maximum frames per second to yield.

        Raises:
            FrameSourceError: If file doesn't exist or can't be opened.
        """
        source = cls()
        path = Path(video_path)

        if not path.exists():
            raise FrameSourceError(f"Video file not found: {video_path}")

        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise FrameSourceError(
                f"Unsupported video format: {path.suffix}. "
                f"Supported: {', '.join(sorted(VIDEO_EXTENSIONS))}"
            )

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise FrameSourceError(f"Failed to open video: {video_path}")

        source._cap = cap
        source._source_path = str(path)
        source._source_type = "video"
        source._total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        source._fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        source._frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        source._frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        source._max_fps = max_fps

        logger.info(
            "frame_source_opened",
            type="video",
            path=str(path),
            resolution=f"{source._frame_width}x{source._frame_height}",
            fps=source._fps,
            total_frames=source._total_frames,
            duration_sec=round(source._total_frames / source._fps, 1) if source._fps > 0 else 0,
        )

        return source

    @classmethod
    def from_webcam(cls, device_index: int = 0, max_fps: int = 30) -> "FrameSource":
        """
        Create frame source from a webcam.

        Args:
            device_index: Camera device index (0 for default).
            max_fps: Maximum frames per second to yield.

        Raises:
            FrameSourceError: If webcam can't be opened.
        """
        source = cls()

        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            raise FrameSourceError(
                f"Failed to open webcam (device index: {device_index}). "
                f"Ensure a camera is connected and accessible."
            )

        source._cap = cap
        source._source_path = f"webcam:{device_index}"
        source._source_type = "webcam"
        source._total_frames = 0  # Unknown for live stream
        source._fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        source._frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        source._frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        source._max_fps = max_fps

        logger.info(
            "frame_source_opened",
            type="webcam",
            device=device_index,
            resolution=f"{source._frame_width}x{source._frame_height}",
            fps=source._fps,
        )

        return source

    def frames(self) -> Generator[Tuple[np.ndarray, int], None, None]:
        """
        Yield frames from the source.

        Yields:
            Tuple of (frame: np.ndarray BGR, frame_number: int)
        """
        if self._source_type == "image":
            yield from self._read_image()
        elif self._source_type in ("video", "webcam"):
            yield from self._read_video_stream()
        else:
            raise FrameSourceError(f"Unknown source type: {self._source_type}")

    def _read_image(self) -> Generator[Tuple[np.ndarray, int], None, None]:
        """Read single image and yield it."""
        frame = cv2.imread(self._source_path)
        if frame is not None:
            yield frame, 1

    def _read_video_stream(self) -> Generator[Tuple[np.ndarray, int], None, None]:
        """Read frames from video or webcam with FPS limiting."""
        if self._cap is None:
            return

        frame_number = 0
        frame_interval = 1.0 / self._max_fps if self._max_fps > 0 else 0

        try:
            while True:
                loop_start = time.perf_counter()

                ret, frame = self._cap.read()
                if not ret:
                    if self._source_type == "video":
                        logger.info("video_ended", frames_read=frame_number)
                    break

                frame_number += 1
                yield frame, frame_number

                # FPS limiting
                elapsed = time.perf_counter() - loop_start
                if frame_interval > elapsed:
                    time.sleep(frame_interval - elapsed)

        except KeyboardInterrupt:
            logger.info("stream_interrupted", frames_read=frame_number)

    @property
    def source_path(self) -> str:
        """Get the source path/identifier."""
        return self._source_path

    @property
    def source_type(self) -> str:
        """Get the source type (image/video/webcam)."""
        return self._source_type

    @property
    def total_frames(self) -> int:
        """Get total frame count (0 for webcam/unknown)."""
        return self._total_frames

    @property
    def fps(self) -> float:
        """Get source FPS."""
        return self._fps

    @property
    def resolution(self) -> Tuple[int, int]:
        """Get (width, height) resolution."""
        return (self._frame_width, self._frame_height)

    def release(self) -> None:
        """Release video capture resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("frame_source_released", source=self._source_path)

    def __del__(self):
        """Ensure resources are released."""
        self.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.release()
