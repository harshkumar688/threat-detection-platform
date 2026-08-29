"""
Unit tests for detection configuration.
"""

import pytest
from src.config import DetectionConfig


class TestDetectionConfig:
    """Tests for DetectionConfig."""

    def test_default_values(self):
        config = DetectionConfig()
        assert config.model_path == "yolov8n.pt"
        assert config.device == "auto"
        assert config.input_size == 640
        assert config.confidence_threshold == 0.5
        assert config.nms_iou_threshold == 0.45
        assert config.draw_bboxes is True
        assert config.max_fps == 30
        assert config.webcam_index == 0

    def test_custom_values(self):
        config = DetectionConfig(
            model_path="/custom/model.pt",
            device="cpu",
            confidence_threshold=0.7,
            input_size=320,
        )
        assert config.model_path == "/custom/model.pt"
        assert config.device == "cpu"
        assert config.confidence_threshold == 0.7
        assert config.input_size == 320

    def test_confidence_range_lower_bound(self):
        config = DetectionConfig(confidence_threshold=0.0)
        assert config.confidence_threshold == 0.0

    def test_confidence_range_upper_bound(self):
        config = DetectionConfig(confidence_threshold=1.0)
        assert config.confidence_threshold == 1.0

    def test_confidence_below_range(self):
        with pytest.raises(Exception):
            DetectionConfig(confidence_threshold=-0.1)

    def test_confidence_above_range(self):
        with pytest.raises(Exception):
            DetectionConfig(confidence_threshold=1.1)

    def test_target_classes_none(self):
        config = DetectionConfig()
        assert config.target_classes is None

    def test_target_classes_list(self):
        config = DetectionConfig(target_classes=["handgun", "person"])
        assert config.target_classes == ["handgun", "person"]

    def test_bbox_thickness_range(self):
        config = DetectionConfig(bbox_thickness=5)
        assert config.bbox_thickness == 5

    def test_max_fps_range(self):
        config = DetectionConfig(max_fps=15)
        assert config.max_fps == 15
