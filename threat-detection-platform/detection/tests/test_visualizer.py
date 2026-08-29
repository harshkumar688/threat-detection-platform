"""
Unit tests for the visualizer module.

Tests bounding box drawing without requiring a real model.
"""

import numpy as np
import pytest

from src.inference.visualizer import (
    draw_detections,
    draw_frame_info,
    get_color_for_class,
)


class TestGetColorForClass:
    """Tests for color assignment."""

    def test_weapon_classes_red(self):
        color = get_color_for_class("handgun")
        assert color[2] > 150  # High red channel (BGR)

    def test_person_green(self):
        color = get_color_for_class("person")
        assert color[1] > 150  # High green channel (BGR)

    def test_unknown_class_uses_default(self):
        color = get_color_for_class("unknown_object")
        # Should return the _default color
        assert color is not None
        assert len(color) == 3


class TestDrawDetections:
    """Tests for drawing bounding boxes on frames."""

    def test_draw_on_frame_returns_same_shape(self, black_frame, sample_frame_result):
        original_shape = black_frame.shape
        result = draw_detections(black_frame, sample_frame_result)
        assert result.shape == original_shape

    def test_draw_modifies_frame(self, black_frame, sample_frame_result):
        # Black frame should have pixels modified after drawing
        original_sum = black_frame.sum()
        draw_detections(black_frame, sample_frame_result)
        assert black_frame.sum() > original_sum  # Pixels were drawn

    def test_draw_empty_detections(self, black_frame):
        from datetime import datetime, timezone
        from src.models import FrameResult

        empty_result = FrameResult(
            frame_number=1,
            timestamp=datetime.now(timezone.utc),
            detections=[],
            frame_width=640,
            frame_height=480,
            inference_time_ms=10.0,
        )
        original = black_frame.copy()
        draw_detections(black_frame, empty_result)
        # Frame should be unchanged with no detections
        assert np.array_equal(black_frame, original)


class TestDrawFrameInfo:
    """Tests for drawing frame info overlay."""

    def test_draw_info_modifies_frame(self, black_frame, sample_frame_result):
        original_sum = black_frame.sum()
        draw_frame_info(black_frame, sample_frame_result)
        assert black_frame.sum() > original_sum

    def test_draw_info_returns_frame(self, black_frame, sample_frame_result):
        result = draw_frame_info(black_frame, sample_frame_result)
        assert result is black_frame  # Same array returned
