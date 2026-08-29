"""
Object Tracker

Core tracking engine that:
1. Receives per-frame detections (from YOLODetector)
2. Associates detections with existing tracks (via IoU + Hungarian)
3. Updates matched tracks
4. Creates new tracks for unmatched detections
5. Ages and removes lost tracks
6. Reports tracking state through TrackedFrame

Design:
- Stateful: maintains internal track list across frames
- Deterministic: same input sequence → same track assignments
- Configurable: thresholds via TrackerConfig
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..logger import get_logger
from ..models import BoundingBox, Detection, FrameResult
from .association import associate_detections_to_tracks, compute_iou_matrix
from .config import TrackerConfig
from .models import Track, TrackedFrame, TrackState

logger = get_logger(__name__)


class ObjectTracker:
    """
    IoU-based multi-object tracker.

    Usage:
        config = TrackerConfig(max_age=30, min_hits=3, iou_threshold=0.3)
        tracker = ObjectTracker(config)

        for frame_result in detection_results:
            tracked_frame = tracker.update(frame_result)
            for track in tracked_frame.active_tracks:
                print(f"Track {track.track_id}: {track.class_name}")
    """

    def __init__(self, config: Optional[TrackerConfig] = None):
        """
        Initialize tracker.

        Args:
            config: Tracker configuration. Uses defaults if None.
        """
        self.config = config or TrackerConfig()
        self._tracks: List[Track] = []
        self._next_id: int = self.config.initial_track_id
        self._frame_count: int = 0

    def update(self, frame_result: FrameResult) -> TrackedFrame:
        """
        Process a new frame's detections and update all tracks.

        This is the main entry point — call once per frame.

        Args:
            frame_result: Detection results from the current frame.

        Returns:
            TrackedFrame with categorized tracks (active, lost, new, removed).
        """
        self._frame_count += 1
        current_frame = frame_result.frame_number
        detections = frame_result.detections

        # Track categorization for this frame's output
        new_tracks: List[Track] = []
        removed_tracks: List[Track] = []

        # --- Step 1: Predict (age all tracks by one frame) ---
        for track in self._tracks:
            track.age += 1

        # --- Step 2: Associate detections to existing tracks ---
        if self._tracks and detections:
            track_boxes = [t.bbox for t in self._tracks]
            det_boxes = [d.bbox for d in detections]

            iou_matrix = compute_iou_matrix(track_boxes, det_boxes)
            matches, unmatched_track_idxs, unmatched_det_idxs = (
                associate_detections_to_tracks(iou_matrix, self.config.iou_threshold)
            )
        elif detections:
            # No existing tracks — all detections are unmatched
            matches = []
            unmatched_track_idxs = []
            unmatched_det_idxs = list(range(len(detections)))
        else:
            # No detections — all tracks are unmatched
            matches = []
            unmatched_track_idxs = list(range(len(self._tracks)))
            unmatched_det_idxs = []

        # --- Step 3: Update matched tracks ---
        for track_idx, det_idx in matches:
            self._update_track(self._tracks[track_idx], detections[det_idx], current_frame)

        # --- Step 4: Mark unmatched tracks as missed ---
        for track_idx in unmatched_track_idxs:
            track = self._tracks[track_idx]
            track.time_since_update += 1
            if track.state == TrackState.CONFIRMED:
                track.state = TrackState.LOST

        # --- Step 5: Create new tracks for unmatched detections ---
        for det_idx in unmatched_det_idxs:
            new_track = self._create_track(detections[det_idx], current_frame)
            self._tracks.append(new_track)
            new_tracks.append(new_track)

        # --- Step 6: Remove dead tracks (exceeded max_age) ---
        surviving_tracks = []
        for track in self._tracks:
            if track.time_since_update > self.config.max_age:
                removed_tracks.append(track)
            else:
                surviving_tracks.append(track)
        self._tracks = surviving_tracks

        # --- Step 7: Promote tentative tracks that reached min_hits ---
        for track in self._tracks:
            if track.state == TrackState.TENTATIVE and track.hits >= self.config.min_hits:
                track.state = TrackState.CONFIRMED
                logger.debug(
                    "track_confirmed",
                    track_id=track.track_id,
                    class_name=track.class_name,
                    hits=track.hits,
                )

        # --- Build output ---
        active_tracks = [t for t in self._tracks if t.time_since_update == 0]
        lost_tracks = [t for t in self._tracks if t.time_since_update > 0]

        if new_tracks:
            logger.debug("new_tracks_created", count=len(new_tracks), frame=current_frame)
        if removed_tracks:
            logger.debug("tracks_removed", count=len(removed_tracks), frame=current_frame)

        return TrackedFrame(
            frame_number=current_frame,
            timestamp=frame_result.timestamp,
            active_tracks=active_tracks,
            lost_tracks=lost_tracks,
            new_tracks=new_tracks,
            removed_tracks=removed_tracks,
            all_tracks=list(self._tracks),
        )

    def _update_track(self, track: Track, detection: Detection, frame_number: int) -> None:
        """Update an existing track with a matched detection."""
        track.bbox = detection.bbox
        track.confidence = detection.confidence
        track.class_name = detection.class_name
        track.class_id = detection.class_id
        track.is_weapon = detection.is_weapon
        track.hits += 1
        track.time_since_update = 0
        track.last_seen_frame = frame_number
        track.confidence_sum += detection.confidence

        # Recover from lost state
        if track.state == TrackState.LOST:
            track.state = TrackState.CONFIRMED

    def _create_track(self, detection: Detection, frame_number: int) -> Track:
        """Create a new track from an unmatched detection."""
        track = Track(
            track_id=self._next_id,
            class_name=detection.class_name,
            class_id=detection.class_id,
            is_weapon=detection.is_weapon,
            bbox=detection.bbox,
            confidence=detection.confidence,
            state=TrackState.TENTATIVE,
            hits=1,
            age=1,
            time_since_update=0,
            first_seen_frame=frame_number,
            last_seen_frame=frame_number,
            confidence_sum=detection.confidence,
        )
        self._next_id += 1
        return track

    def reset(self) -> None:
        """Reset tracker state (clear all tracks)."""
        self._tracks.clear()
        self._next_id = self.config.initial_track_id
        self._frame_count = 0
        logger.info("tracker_reset")

    @property
    def track_count(self) -> int:
        """Total number of tracks currently maintained (including lost)."""
        return len(self._tracks)

    @property
    def confirmed_count(self) -> int:
        """Number of confirmed tracks."""
        return sum(1 for t in self._tracks if t.is_confirmed)

    @property
    def tracks(self) -> List[Track]:
        """Get a copy of all current tracks."""
        return list(self._tracks)

    def get_track_by_id(self, track_id: int) -> Optional[Track]:
        """Look up a track by its ID. Returns None if not found."""
        for track in self._tracks:
            if track.track_id == track_id:
                return track
        return None

    def get_info(self) -> dict:
        """Get tracker status."""
        return {
            "total_tracks": self.track_count,
            "confirmed_tracks": self.confirmed_count,
            "frames_processed": self._frame_count,
            "next_track_id": self._next_id,
            "config": {
                "max_age": self.config.max_age,
                "min_hits": self.config.min_hits,
                "iou_threshold": self.config.iou_threshold,
            },
        }
