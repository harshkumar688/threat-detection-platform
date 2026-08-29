"""
Tracking Data Models

Defines the data structures for tracked objects.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from ..models import BoundingBox, Detection


class TrackState(str, Enum):
    """Track lifecycle state."""

    TENTATIVE = "tentative"    # New track, not yet confirmed (hits < min_hits)
    CONFIRMED = "confirmed"    # Active confirmed track
    LOST = "lost"              # Track missed in recent frame(s), not yet deleted


@dataclass
class Track:
    """
    A single tracked object.

    Represents the persistent identity of an object across multiple frames.
    """

    track_id: int                     # Unique, stable identifier
    class_name: str                   # Detected class (most recent)
    class_id: int                     # Numeric class ID
    is_weapon: bool                   # Whether this is a weapon track
    bbox: BoundingBox                 # Most recent bounding box
    confidence: float                 # Most recent confidence

    state: TrackState = TrackState.TENTATIVE  # Lifecycle state

    # Counters
    hits: int = 0                     # Total frames where this track was matched
    age: int = 0                      # Total frames since track creation
    time_since_update: int = 0        # Frames since last successful match (0 = matched this frame)

    # History
    first_seen_frame: int = 0         # Frame number when first detected
    last_seen_frame: int = 0          # Frame number of most recent match
    confidence_sum: float = 0.0       # Sum of all matched confidences (for avg)

    @property
    def avg_confidence(self) -> float:
        """Average confidence across all matched frames."""
        return self.confidence_sum / self.hits if self.hits > 0 else 0.0

    @property
    def duration_frames(self) -> int:
        """How many frames this track has existed."""
        return self.age

    @property
    def is_confirmed(self) -> bool:
        """Whether track is confirmed (met min_hits threshold)."""
        return self.state == TrackState.CONFIRMED

    @property
    def is_lost(self) -> bool:
        """Whether track is currently lost (not matched recently)."""
        return self.state == TrackState.LOST

    @property
    def is_tentative(self) -> bool:
        """Whether track is tentative (not yet confirmed)."""
        return self.state == TrackState.TENTATIVE

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "class_id": self.class_id,
            "is_weapon": self.is_weapon,
            "bbox": {
                "x1": round(self.bbox.x1, 4),
                "y1": round(self.bbox.y1, 4),
                "x2": round(self.bbox.x2, 4),
                "y2": round(self.bbox.y2, 4),
            },
            "confidence": round(self.confidence, 4),
            "avg_confidence": round(self.avg_confidence, 4),
            "state": self.state.value,
            "hits": self.hits,
            "age": self.age,
            "time_since_update": self.time_since_update,
            "first_seen_frame": self.first_seen_frame,
            "last_seen_frame": self.last_seen_frame,
        }


@dataclass
class TrackedFrame:
    """
    Tracking results for a single frame.

    Produced by ObjectTracker.update() — this is what downstream modules consume.
    """

    frame_number: int
    timestamp: datetime
    active_tracks: List[Track]       # Confirmed tracks matched this frame
    lost_tracks: List[Track]         # Tracks not matched (still within max_age)
    new_tracks: List[Track]          # Newly created tracks this frame
    removed_tracks: List[Track]      # Tracks deleted this frame (exceeded max_age)
    all_tracks: List[Track]          # Every track regardless of state

    @property
    def confirmed_weapon_tracks(self) -> List[Track]:
        """Active confirmed weapon tracks."""
        return [t for t in self.active_tracks if t.is_weapon and t.is_confirmed]

    @property
    def confirmed_person_tracks(self) -> List[Track]:
        """Active confirmed person tracks."""
        return [t for t in self.active_tracks if t.class_name == "person" and t.is_confirmed]

    @property
    def total_active(self) -> int:
        """Count of active (matched this frame) tracks."""
        return len(self.active_tracks)

    @property
    def total_lost(self) -> int:
        """Count of lost tracks."""
        return len(self.lost_tracks)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "frame_number": self.frame_number,
            "timestamp": self.timestamp.isoformat(),
            "active_tracks": [t.to_dict() for t in self.active_tracks],
            "lost_tracks": [t.to_dict() for t in self.lost_tracks],
            "new_tracks": [t.to_dict() for t in self.new_tracks],
            "removed_tracks": [t.to_dict() for t in self.removed_tracks],
            "total_active": self.total_active,
            "total_lost": self.total_lost,
        }
