"""
Face Detection (localization only) — Backend copy

Uses OpenCV's pretrained Haar-cascade frontal-face detector to find
face-shaped regions in a frame. See app/privacy/config.py for the full
scope statement and hard boundaries (no recognition, no embeddings, no
identity inference).

This mirrors detection/src/privacy/face_detector.py. It is duplicated
rather than imported because backend and detection are independently
deployable services with separate dependency sets (see
REPOSITORY_STRUCTURE.md) — there is no shared package between them.
"""

import logging
import os
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# (x, y, w, h) in pixel coordinates
FaceBox = Tuple[int, int, int, int]


class FaceDetectorError(Exception):
    """Raised when the face detector cannot be initialized."""
    pass


class FaceDetector:
    """
    Wraps OpenCV's pretrained Haar-cascade frontal-face classifier.

    Usage:
        detector = FaceDetector()
        boxes = detector.detect(frame)  # [(x, y, w, h), ...]
    """

    _CASCADE_FILENAME = "haarcascade_frontalface_default.xml"

    def __init__(
        self,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_face_ratio: float = 0.02,
    ):
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_face_ratio = min_face_ratio
        self._cascade: Optional["cv2.CascadeClassifier"] = None

    def _ensure_loaded(self):
        if self._cascade is not None:
            return self._cascade

        cascade_path = os.path.join(cv2.data.haarcascades, self._CASCADE_FILENAME)
        if not os.path.exists(cascade_path):
            raise FaceDetectorError(
                f"Haar cascade file not found: {cascade_path}. "
                "Ensure opencv-python(-headless) is installed with bundled cascade data."
            )

        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            raise FaceDetectorError(f"Failed to load Haar cascade from: {cascade_path}")

        self._cascade = cascade
        return cascade

    def detect(self, frame: Optional[np.ndarray]) -> List[FaceBox]:
        """
        Detect face-shaped regions in a BGR frame.

        Returns an empty list for frames with no detected faces, invalid
        frames, or if the cascade fails on a specific frame — this method
        never raises for "no face found", only for detector init failure.
        """
        if frame is None or frame.size == 0:
            return []

        cascade = self._ensure_loaded()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_width = frame.shape[1]
        min_size = max(1, int(frame_width * self.min_face_ratio))

        try:
            raw_boxes = cascade.detectMultiScale(
                gray,
                scaleFactor=self.scale_factor,
                minNeighbors=self.min_neighbors,
                minSize=(min_size, min_size),
            )
        except cv2.error as e:
            logger.warning("Face detection failed for frame: %s", e)
            return []

        return [tuple(int(v) for v in box) for box in raw_boxes]
