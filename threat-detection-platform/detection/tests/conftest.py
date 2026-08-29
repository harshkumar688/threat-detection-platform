"""
Shared test fixtures for the detection module.
"""

import numpy as np
import pytest

from src.config import DetectionConfig
from src.models import BoundingBox, Detection, FrameResult
from datetime import datetime, timezone


@pytest.fixture
def sample_config():
    """Default test configuration."""
    return DetectionConfig(
        model_path="yolov8n.pt",
        device="cpu",
        confidence_threshold=0.5,
        nms_iou_threshold=0.45,
        input_size=640,
    )


@pytest.fixture
def sample_frame():
    """Create a sample BGR frame (640x480, random pixels)."""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def black_frame():
    """Create a black BGR frame (640x480)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_bbox():
    """A sample bounding box (normalized)."""
    return BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8)


@pytest.fixture
def sample_detection(sample_bbox):
    """A sample detection."""
    return Detection(
        class_id=0,
        class_name="handgun",
        confidence=0.87,
        bbox=sample_bbox,
        is_weapon=True,
    )


@pytest.fixture
def sample_person_detection():
    """A sample person detection."""
    return Detection(
        class_id=3,
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=0.2, y1=0.1, x2=0.6, y2=0.9),
        is_weapon=False,
    )


@pytest.fixture
def sample_frame_result(sample_detection, sample_person_detection):
    """A sample FrameResult with mixed detections."""
    return FrameResult(
        frame_number=42,
        timestamp=datetime(2026, 8, 17, 14, 30, 0, tzinfo=timezone.utc),
        detections=[sample_detection, sample_person_detection],
        frame_width=640,
        frame_height=480,
        inference_time_ms=28.5,
        source="test_video.mp4",
    )
