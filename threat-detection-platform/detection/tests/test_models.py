"""
Unit tests for detection data models.

Tests BoundingBox, Detection, FrameResult without requiring a YOLO model.
"""

import pytest
from datetime import datetime, timezone

from src.models import (
    BoundingBox,
    Detection,
    FrameResult,
    WEAPON_CLASSES,
    is_weapon_class,
)


class TestBoundingBox:
    """Tests for the BoundingBox dataclass."""

    def test_basic_creation(self):
        bbox = BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8)
        assert bbox.x1 == 0.1
        assert bbox.y1 == 0.2
        assert bbox.x2 == 0.5
        assert bbox.y2 == 0.8

    def test_width(self):
        bbox = BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8)
        assert abs(bbox.width - 0.4) < 1e-6

    def test_height(self):
        bbox = BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8)
        assert abs(bbox.height - 0.6) < 1e-6

    def test_center(self):
        bbox = BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0)
        cx, cy = bbox.center
        assert abs(cx - 0.5) < 1e-6
        assert abs(cy - 0.5) < 1e-6

    def test_area(self):
        bbox = BoundingBox(x1=0.0, y1=0.0, x2=0.5, y2=0.5)
        assert abs(bbox.area - 0.25) < 1e-6

    def test_to_pixel_coords(self):
        bbox = BoundingBox(x1=0.25, y1=0.5, x2=0.75, y2=1.0)
        px1, py1, px2, py2 = bbox.to_pixel_coords(800, 600)
        assert px1 == 200
        assert py1 == 300
        assert px2 == 600
        assert py2 == 600

    def test_is_valid_true(self):
        bbox = BoundingBox(x1=0.1, y1=0.2, x2=0.5, y2=0.8)
        assert bbox.is_valid() is True

    def test_is_valid_false_inverted_x(self):
        bbox = BoundingBox(x1=0.5, y1=0.2, x2=0.1, y2=0.8)
        assert bbox.is_valid() is False

    def test_is_valid_false_inverted_y(self):
        bbox = BoundingBox(x1=0.1, y1=0.8, x2=0.5, y2=0.2)
        assert bbox.is_valid() is False

    def test_is_valid_false_out_of_range(self):
        bbox = BoundingBox(x1=-0.1, y1=0.2, x2=0.5, y2=0.8)
        assert bbox.is_valid() is False

    def test_is_valid_false_exceeds_one(self):
        bbox = BoundingBox(x1=0.1, y1=0.2, x2=1.1, y2=0.8)
        assert bbox.is_valid() is False

    def test_zero_area_is_invalid(self):
        bbox = BoundingBox(x1=0.5, y1=0.5, x2=0.5, y2=0.5)
        assert bbox.is_valid() is False


class TestDetection:
    """Tests for the Detection dataclass."""

    def test_creation(self, sample_detection):
        assert sample_detection.class_id == 0
        assert sample_detection.class_name == "handgun"
        assert sample_detection.confidence == 0.87
        assert sample_detection.is_weapon is True

    def test_to_dict(self, sample_detection):
        d = sample_detection.to_dict()
        assert d["class_name"] == "handgun"
        assert d["confidence"] == 0.87
        assert d["is_weapon"] is True
        assert "x1" in d["bbox"]
        assert "y2" in d["bbox"]

    def test_non_weapon(self, sample_person_detection):
        assert sample_person_detection.is_weapon is False
        assert sample_person_detection.class_name == "person"


class TestFrameResult:
    """Tests for the FrameResult dataclass."""

    def test_detection_count(self, sample_frame_result):
        assert sample_frame_result.detection_count == 2

    def test_has_weapons(self, sample_frame_result):
        assert sample_frame_result.has_weapons is True

    def test_weapon_detections(self, sample_frame_result):
        weapons = sample_frame_result.weapon_detections
        assert len(weapons) == 1
        assert weapons[0].class_name == "handgun"

    def test_person_detections(self, sample_frame_result):
        persons = sample_frame_result.person_detections
        assert len(persons) == 1
        assert persons[0].class_name == "person"

    def test_no_weapons(self, sample_person_detection):
        result = FrameResult(
            frame_number=1,
            timestamp=datetime.now(timezone.utc),
            detections=[sample_person_detection],
            frame_width=640,
            frame_height=480,
            inference_time_ms=20.0,
        )
        assert result.has_weapons is False
        assert len(result.weapon_detections) == 0

    def test_empty_detections(self):
        result = FrameResult(
            frame_number=1,
            timestamp=datetime.now(timezone.utc),
            detections=[],
            frame_width=640,
            frame_height=480,
            inference_time_ms=15.0,
        )
        assert result.detection_count == 0
        assert result.has_weapons is False

    def test_to_dict(self, sample_frame_result):
        d = sample_frame_result.to_dict()
        assert d["frame_number"] == 42
        assert d["detection_count"] == 2
        assert d["has_weapons"] is True
        assert len(d["detections"]) == 2
        assert "timestamp" in d
        assert d["inference_time_ms"] == 28.5


class TestIsWeaponClass:
    """Tests for the is_weapon_class helper."""

    def test_handgun(self):
        assert is_weapon_class("handgun") is True

    def test_rifle(self):
        assert is_weapon_class("rifle") is True

    def test_knife(self):
        assert is_weapon_class("knife") is True

    def test_person_not_weapon(self):
        assert is_weapon_class("person") is False

    def test_car_not_weapon(self):
        assert is_weapon_class("car") is False

    def test_case_insensitive(self):
        assert is_weapon_class("Handgun") is True
        assert is_weapon_class("RIFLE") is True

    def test_gun_variant(self):
        assert is_weapon_class("gun") is True
        assert is_weapon_class("pistol") is True
