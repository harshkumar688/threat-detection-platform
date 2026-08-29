"""
Face Detection (localization only)

Uses OpenCV's pretrained Haar-cascade frontal-face detector to find
face-shaped regions in a frame.

IMPORTANT — what this is and is not:
- This is FACE LOCALIZATION, not face recognition. It returns bounding
  boxes for regions that look like faces. It does not identify, name,
  match, or distinguish one detected face from another.
- No facial embeddings, landmarks-for-identity, or biometric templates
  are computed, transmitted, or stored anywhere in this module.
- Detection quality is a known limitation of the classical Haar-cascade
  approach: it can miss non-frontal faces, faces in low light, or very
  small faces, and can occasionally false-positive on face-like textures.
  This module is intended as a best-effort privacy safeguard, not a
  guarantee that every face in every frame will be found.
"""

import logging
import os
from typing import List, Tuple

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
        """
        Args:
            scale_factor: How much the image size is reduced at each
                image scale during the cascade's multi-scale search.
            min_neighbors: How many neighbor detections are required to
                retain a candidate face box; higher = fewer false positives.
            min_face_ratio: Minimum face box width as a ratio of frame
                width. Filters out spuriously tiny detections.
        """
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_face_ratio = min_face_ratio
        self._cascade: cv2.CascadeClassifier | None = None

    def _ensure_loaded(self) -> cv2.CascadeClassifier:
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

    def detect(self, frame: np.ndarray) -> List[FaceBox]:
        """
        Detect face-shaped regions in a BGR frame.

        Args:
            frame: BGR numpy array (H, W, 3).

        Returns:
            List of (x, y, w, h) pixel boxes, one per detected face-like
            region. Empty list if none are found. Never raises for a
            frame that simply contains no faces.
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
