"""
Face Anonymization

Applies Gaussian blur or pixelation to detected face regions in a frame.

This module never performs identification — it only obscures whatever
face-shaped regions FaceDetector locates. The transformation is applied
destructively to the frame data itself: once anonymized, the original
pixel values for that region are gone from the returned array. Callers
that discard the pre-anonymization frame (as recommended) do not retain
any way to recover the original face pixels.
"""

import logging
from typing import List

import cv2
import numpy as np

from .config import PrivacyConfig, PrivacyMode
from .face_detector import FaceBox, FaceDetector

logger = logging.getLogger(__name__)


class FaceAnonymizer:
    """
    Applies configurable face anonymization to frames.

    Usage:
        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR)
        anonymizer = FaceAnonymizer(config)
        anonymized_frame, face_count = anonymizer.process(frame)
    """

    def __init__(self, config: PrivacyConfig, detector: FaceDetector | None = None):
        self.config = config
        self._detector = detector or FaceDetector(
            scale_factor=config.detection_scale_factor,
            min_neighbors=config.detection_min_neighbors,
            min_face_ratio=config.detection_min_face_ratio,
        )

    def process(self, frame: np.ndarray) -> tuple[np.ndarray, int]:
        """
        Apply the configured privacy mode to a frame.

        Args:
            frame: BGR numpy array. Modified in place AND returned.

        Returns:
            Tuple of (processed_frame, faces_anonymized_count).
            If mode is OFF, returns the frame unmodified and count 0.
        """
        if self.config.mode == PrivacyMode.OFF:
            return frame, 0

        boxes = self._detector.detect(frame)
        if not boxes:
            return frame, 0

        expanded_boxes = [self._expand_box(box, frame.shape) for box in boxes]

        for x, y, w, h in expanded_boxes:
            region = frame[y:y + h, x:x + w]
            if region.size == 0:
                continue

            if self.config.mode == PrivacyMode.FACE_BLUR:
                frame[y:y + h, x:x + w] = self._blur_region(region)
            elif self.config.mode == PrivacyMode.FACE_PIXELATE:
                frame[y:y + h, x:x + w] = self._pixelate_region(region)

        return frame, len(expanded_boxes)

    def _expand_box(self, box: FaceBox, frame_shape: tuple) -> FaceBox:
        """Expand a face box by the configured margin, clamped to frame bounds."""
        x, y, w, h = box
        frame_h, frame_w = frame_shape[:2]

        margin_x = int(w * self.config.expand_box_ratio)
        margin_y = int(h * self.config.expand_box_ratio)

        new_x = max(0, x - margin_x)
        new_y = max(0, y - margin_y)
        new_w = min(frame_w - new_x, w + 2 * margin_x)
        new_h = min(frame_h - new_y, h + 2 * margin_y)

        return (new_x, new_y, new_w, new_h)

    def _blur_region(self, region: np.ndarray) -> np.ndarray:
        """Apply Gaussian blur strong enough to obscure facial features."""
        h, w = region.shape[:2]
        shorter_side = min(h, w)

        kernel = int(shorter_side * self.config.blur_kernel_ratio)
        kernel = max(3, kernel)
        if kernel % 2 == 0:
            kernel += 1  # GaussianBlur requires an odd kernel size

        return cv2.GaussianBlur(region, (kernel, kernel), 0)

    def _pixelate_region(self, region: np.ndarray) -> np.ndarray:
        """Apply mosaic/pixelation by downsampling then upsampling with nearest-neighbor."""
        h, w = region.shape[:2]
        block = max(2, self.config.pixelate_block_size)

        small_w = max(1, w // block)
        small_h = max(1, h // block)

        small = cv2.resize(region, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
