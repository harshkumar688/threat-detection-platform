"""
Unit tests for the object tracking module.

Tests track lifecycle, association, and state transitions
WITHOUT requiring a YOLO model.
"""

import pytest
from datetime import datetime, timezone

from src.models import BoundingBox, Detection, FrameResult
from src.tracking import ObjectTracker, TrackerConfig, Track, TrackState, TrackedFrame
from src.tracking.association import compute_iou, compute_iou_matrix, associate_detections_to_tracks


# =============================================================================
# Helpers
# =============================================================================

def make_detection(x1, y1, x2, y2, class_name="person", confidence=0.9, is_weapon=False):
    """Create a detection for testing."""
    return Detection(
        class_id=0,
        class_name=class_name,
        confidence=confidence,
        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        is_weapon=is_weapon,
    )


def make_frame_result(detections, frame_number=1):
    """Create a FrameResult for testing."""
    return FrameResult(
        frame_number=frame_number,
        timestamp=datetime.now(timezone.utc),
        detections=detections,
        frame_width=640,
        frame_height=480,
        inference_time_ms=20.0,
        source="test",
    )


# =============================================================================
# IoU Tests
# =============================================================================

class TestIoU:
    """Tests for IoU computation."""

    def test_identical_boxes(self):
        box = BoundingBox(x1=0.2, y1=0.2, x2=0.8, y2=0.8)
        assert abs(compute_iou(box, box) - 1.0) < 1e-6

    def test_no_overlap(self):
        box_a = BoundingBox(x1=0.0, y1=0.0, x2=0.3, y2=0.3)
        box_b = BoundingBox(x1=0.5, y1=0.5, x2=0.8, y2=0.8)
        assert compute_iou(box_a, box_b) == 0.0

    def test_partial_overlap(self):
        box_a = BoundingBox(x1=0.0, y1=0.0, x2=0.5, y2=0.5)
        box_b = BoundingBox(x1=0.25, y1=0.25, x2=0.75, y2=0.75)
        iou = compute_iou(box_a, box_b)
        # Intersection: (0.25,0.25)→(0.5,0.5) = 0.25 * 0.25 = 0.0625
        # Union: 0.25 + 0.25 - 0.0625 = 0.4375
        expected = 0.0625 / 0.4375
        assert abs(iou - expected) < 1e-6

    def test_contained_box(self):
        big = BoundingBox(x1=0.0, y1=0.0, x2=1.0, y2=1.0)
        small = BoundingBox(x1=0.4, y1=0.4, x2=0.6, y2=0.6)
        iou = compute_iou(big, small)
        # Intersection = small area = 0.04
        # Union = 1.0 + 0.04 - 0.04 = 1.0
        expected = 0.04 / 1.0
        assert abs(iou - expected) < 1e-6

    def test_touching_boxes_zero_iou(self):
        box_a = BoundingBox(x1=0.0, y1=0.0, x2=0.5, y2=0.5)
        box_b = BoundingBox(x1=0.5, y1=0.0, x2=1.0, y2=0.5)
        assert compute_iou(box_a, box_b) == 0.0


class TestIoUMatrix:
    """Tests for IoU matrix computation."""

    def test_empty_tracks(self):
        dets = [BoundingBox(0.1, 0.1, 0.5, 0.5)]
        matrix = compute_iou_matrix([], dets)
        assert matrix.shape == (0, 1)

    def test_empty_detections(self):
        tracks = [BoundingBox(0.1, 0.1, 0.5, 0.5)]
        matrix = compute_iou_matrix(tracks, [])
        assert matrix.shape == (1, 0)

    def test_square_matrix(self):
        boxes = [
            BoundingBox(0.0, 0.0, 0.5, 0.5),
            BoundingBox(0.5, 0.5, 1.0, 1.0),
        ]
        matrix = compute_iou_matrix(boxes, boxes)
        assert matrix.shape == (2, 2)
        assert abs(matrix[0, 0] - 1.0) < 1e-6  # Self-IoU
        assert abs(matrix[1, 1] - 1.0) < 1e-6
        assert matrix[0, 1] == 0.0  # No overlap


class TestAssociation:
    """Tests for detection-to-track association."""

    def test_perfect_match(self):
        import numpy as np
        iou_matrix = np.array([[0.9, 0.1], [0.1, 0.8]])
        matches, unmatched_t, unmatched_d = associate_detections_to_tracks(iou_matrix, 0.3)
        assert len(matches) == 2
        assert (0, 0) in matches
        assert (1, 1) in matches
        assert len(unmatched_t) == 0
        assert len(unmatched_d) == 0

    def test_no_match_below_threshold(self):
        import numpy as np
        iou_matrix = np.array([[0.1, 0.05], [0.02, 0.15]])
        matches, unmatched_t, unmatched_d = associate_detections_to_tracks(iou_matrix, 0.3)
        assert len(matches) == 0
        assert len(unmatched_t) == 2
        assert len(unmatched_d) == 2

    def test_more_dets_than_tracks(self):
        import numpy as np
        iou_matrix = np.array([[0.8, 0.1, 0.05]])  # 1 track, 3 dets
        matches, unmatched_t, unmatched_d = associate_detections_to_tracks(iou_matrix, 0.3)
        assert len(matches) == 1
        assert matches[0] == (0, 0)
        assert len(unmatched_t) == 0
        assert len(unmatched_d) == 2

    def test_more_tracks_than_dets(self):
        import numpy as np
        iou_matrix = np.array([[0.9], [0.1], [0.05]])  # 3 tracks, 1 det
        matches, unmatched_t, unmatched_d = associate_detections_to_tracks(iou_matrix, 0.3)
        assert len(matches) == 1
        assert matches[0] == (0, 0)
        assert len(unmatched_t) == 2
        assert len(unmatched_d) == 0


# =============================================================================
# Tracker Lifecycle Tests
# =============================================================================

class TestTrackerBasics:
    """Basic tracker operation tests."""

    def test_empty_frame(self):
        tracker = ObjectTracker(TrackerConfig(min_hits=1))
        result = tracker.update(make_frame_result([]))
        assert result.total_active == 0
        assert result.total_lost == 0
        assert len(result.new_tracks) == 0

    def test_single_detection_creates_track(self):
        tracker = ObjectTracker(TrackerConfig(min_hits=1))
        det = make_detection(0.1, 0.1, 0.5, 0.5)
        result = tracker.update(make_frame_result([det]))
        assert len(result.new_tracks) == 1
        assert result.new_tracks[0].track_id == 1
        assert result.new_tracks[0].class_name == "person"

    def test_track_ids_increment(self):
        tracker = ObjectTracker(TrackerConfig(min_hits=1))
        det_a = make_detection(0.0, 0.0, 0.3, 0.3)
        det_b = make_detection(0.7, 0.7, 1.0, 1.0)
        result = tracker.update(make_frame_result([det_a, det_b]))
        ids = [t.track_id for t in result.new_tracks]
        assert ids == [1, 2]

    def test_stable_track_id_across_frames(self):
        tracker = ObjectTracker(TrackerConfig(min_hits=1, iou_threshold=0.2))
        # Frame 1: object at position A
        det1 = make_detection(0.4, 0.4, 0.6, 0.6)
        result1 = tracker.update(make_frame_result([det1], frame_number=1))
        track_id = result1.active_tracks[0].track_id

        # Frame 2: object moved slightly
        det2 = make_detection(0.42, 0.42, 0.62, 0.62)
        result2 = tracker.update(make_frame_result([det2], frame_number=2))
        assert result2.active_tracks[0].track_id == track_id  # Same ID!

    def test_two_objects_maintain_separate_ids(self):
        tracker = ObjectTracker(TrackerConfig(min_hits=1, iou_threshold=0.2))

        # Frame 1: two objects far apart
        dets1 = [
            make_detection(0.0, 0.0, 0.2, 0.2, class_name="person"),
            make_detection(0.8, 0.8, 1.0, 1.0, class_name="handgun", is_weapon=True),
        ]
        result1 = tracker.update(make_frame_result(dets1, frame_number=1))
        id_person = [t for t in result1.active_tracks if t.class_name == "person"][0].track_id
        id_weapon = [t for t in result1.active_tracks if t.class_name == "handgun"][0].track_id

        # Frame 2: both objects still present, slightly moved
        dets2 = [
            make_detection(0.02, 0.02, 0.22, 0.22, class_name="person"),
            make_detection(0.78, 0.78, 0.98, 0.98, class_name="handgun", is_weapon=True),
        ]
        result2 = tracker.update(make_frame_result(dets2, frame_number=2))
        ids = {t.class_name: t.track_id for t in result2.active_tracks}
        assert ids["person"] == id_person
        assert ids["handgun"] == id_weapon


class TestTrackLifecycle:
    """Tests for track state transitions."""

    def test_tentative_to_confirmed(self):
        config = TrackerConfig(min_hits=3, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        det = make_detection(0.4, 0.4, 0.6, 0.6)

        # Frame 1: tentative
        r1 = tracker.update(make_frame_result([det], frame_number=1))
        assert r1.active_tracks[0].state == TrackState.TENTATIVE

        # Frame 2: still tentative (hits=2)
        r2 = tracker.update(make_frame_result([det], frame_number=2))
        assert r2.active_tracks[0].state == TrackState.TENTATIVE

        # Frame 3: confirmed (hits=3 >= min_hits)
        r3 = tracker.update(make_frame_result([det], frame_number=3))
        assert r3.active_tracks[0].state == TrackState.CONFIRMED

    def test_confirmed_to_lost(self):
        config = TrackerConfig(min_hits=1, max_age=5, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        det = make_detection(0.4, 0.4, 0.6, 0.6)

        # Frame 1: create and confirm
        tracker.update(make_frame_result([det], frame_number=1))

        # Frame 2: object disappears
        r2 = tracker.update(make_frame_result([], frame_number=2))
        assert len(r2.lost_tracks) == 1
        assert r2.lost_tracks[0].state == TrackState.LOST

    def test_lost_track_recovery(self):
        config = TrackerConfig(min_hits=1, max_age=10, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        det = make_detection(0.4, 0.4, 0.6, 0.6)

        # Frame 1: create
        tracker.update(make_frame_result([det], frame_number=1))

        # Frame 2-4: object gone (lost)
        for frame in range(2, 5):
            tracker.update(make_frame_result([], frame_number=frame))

        # Frame 5: object returns to same position
        r5 = tracker.update(make_frame_result([det], frame_number=5))
        # Track should be recovered (same ID, back to confirmed)
        assert len(r5.active_tracks) == 1
        assert r5.active_tracks[0].track_id == 1
        assert r5.active_tracks[0].state == TrackState.CONFIRMED

    def test_track_removed_after_max_age(self):
        config = TrackerConfig(min_hits=1, max_age=3, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        det = make_detection(0.4, 0.4, 0.6, 0.6)

        # Frame 1: create
        tracker.update(make_frame_result([det], frame_number=1))

        # Frames 2-5: no detections (exceeds max_age=3)
        removed = None
        for frame in range(2, 6):
            result = tracker.update(make_frame_result([], frame_number=frame))
            if result.removed_tracks:
                removed = result.removed_tracks
                break

        assert removed is not None
        assert removed[0].track_id == 1

    def test_track_count_after_removal(self):
        config = TrackerConfig(min_hits=1, max_age=2, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        det = make_detection(0.4, 0.4, 0.6, 0.6)
        tracker.update(make_frame_result([det], frame_number=1))
        assert tracker.track_count == 1

        # Miss for max_age+1 frames
        for f in range(2, 5):
            tracker.update(make_frame_result([], frame_number=f))

        assert tracker.track_count == 0


class TestTrackerState:
    """Tests for tracker state inspection."""

    def test_reset(self):
        config = TrackerConfig(min_hits=1)
        tracker = ObjectTracker(config)

        det = make_detection(0.3, 0.3, 0.7, 0.7)
        tracker.update(make_frame_result([det]))
        assert tracker.track_count > 0

        tracker.reset()
        assert tracker.track_count == 0
        assert tracker._next_id == config.initial_track_id

    def test_get_track_by_id(self):
        config = TrackerConfig(min_hits=1)
        tracker = ObjectTracker(config)

        det = make_detection(0.3, 0.3, 0.7, 0.7)
        tracker.update(make_frame_result([det]))

        track = tracker.get_track_by_id(1)
        assert track is not None
        assert track.track_id == 1

        missing = tracker.get_track_by_id(999)
        assert missing is None

    def test_get_info(self):
        config = TrackerConfig(min_hits=1, max_age=30, iou_threshold=0.3)
        tracker = ObjectTracker(config)

        info = tracker.get_info()
        assert info["total_tracks"] == 0
        assert info["config"]["max_age"] == 30
        assert info["config"]["iou_threshold"] == 0.3

    def test_hits_counter(self):
        config = TrackerConfig(min_hits=1, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        det = make_detection(0.4, 0.4, 0.6, 0.6)

        for frame in range(1, 6):
            tracker.update(make_frame_result([det], frame_number=frame))

        track = tracker.get_track_by_id(1)
        assert track.hits == 5
        assert track.age == 5

    def test_avg_confidence(self):
        config = TrackerConfig(min_hits=1, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        # Three frames with different confidences
        for frame, conf in [(1, 0.8), (2, 0.9), (3, 0.7)]:
            det = make_detection(0.4, 0.4, 0.6, 0.6, confidence=conf)
            tracker.update(make_frame_result([det], frame_number=frame))

        track = tracker.get_track_by_id(1)
        expected_avg = (0.8 + 0.9 + 0.7) / 3
        assert abs(track.avg_confidence - expected_avg) < 1e-6


class TestTrackedFrame:
    """Tests for TrackedFrame output model."""

    def test_confirmed_weapon_tracks(self):
        config = TrackerConfig(min_hits=1, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        dets = [
            make_detection(0.1, 0.1, 0.3, 0.3, class_name="handgun", is_weapon=True),
            make_detection(0.7, 0.7, 0.9, 0.9, class_name="person"),
        ]
        result = tracker.update(make_frame_result(dets))

        assert len(result.confirmed_weapon_tracks) == 1
        assert result.confirmed_weapon_tracks[0].class_name == "handgun"

    def test_confirmed_person_tracks(self):
        config = TrackerConfig(min_hits=1, iou_threshold=0.2)
        tracker = ObjectTracker(config)

        dets = [make_detection(0.4, 0.4, 0.6, 0.6, class_name="person")]
        result = tracker.update(make_frame_result(dets))

        assert len(result.confirmed_person_tracks) == 1

    def test_to_dict(self):
        config = TrackerConfig(min_hits=1)
        tracker = ObjectTracker(config)

        det = make_detection(0.3, 0.3, 0.7, 0.7)
        result = tracker.update(make_frame_result([det]))

        d = result.to_dict()
        assert "frame_number" in d
        assert "active_tracks" in d
        assert "total_active" in d
        assert d["total_active"] == 1
