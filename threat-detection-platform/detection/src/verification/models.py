"""
Verification Data Models

Defines threat states and verification result structures.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Deque, List, Optional

from ..models import BoundingBox


class ThreatState(str, Enum):
    """Threat verification state machine states."""

    NO_THREAT = "no_threat"
    """Weapon track exists but detection evidence is insufficient."""

    CANDIDATE = "candidate"
    """Met initial N/M window threshold. Awaiting sustained confirmation."""

    CONFIRMED = "confirmed"
    """Verified threat. Downstream should create incident + alert."""

    RESOLVED = "resolved"
    """Threat is no longer active (track lost or manually resolved)."""


@dataclass
class VerifiedThreat:
    """
    A weapon track under temporal verification.

    Maintained per weapon track_id. Holds the sliding window history
    and current verification state.
    """

    track_id: int
    class_name: str
    is_weapon: bool

    # State
    state: ThreatState = ThreatState.NO_THREAT

    # Sliding window: deque of (detected: bool, confidence: float) per frame
    window: Deque = field(default_factory=deque)

    # Counters
    frames_as_candidate: int = 0       # How long in CANDIDATE state
    frames_as_confirmed: int = 0       # How long in CONFIRMED state
    consecutive_misses: int = 0        # Current streak of missed frames
    total_hits: int = 0                # Lifetime hit count
    total_frames: int = 0              # Lifetime frame count

    # Metadata
    first_seen_frame: int = 0
    last_seen_frame: int = 0
    last_confidence: float = 0.0
    bbox: Optional[BoundingBox] = None

    # Timestamps
    candidate_since_frame: Optional[int] = None
    confirmed_at_frame: Optional[int] = None
    resolved_at_frame: Optional[int] = None

    @property
    def window_hits(self) -> int:
        """Number of hits in the current sliding window."""
        return sum(1 for hit, _ in self.window if hit)

    @property
    def window_avg_confidence(self) -> float:
        """Average confidence of hits in the current window."""
        confidences = [conf for hit, conf in self.window if hit]
        return sum(confidences) / len(confidences) if confidences else 0.0

    @property
    def is_active(self) -> bool:
        """Whether this threat is in an active state (not resolved)."""
        return self.state in (ThreatState.NO_THREAT, ThreatState.CANDIDATE, ThreatState.CONFIRMED)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "state": self.state.value,
            "window_hits": self.window_hits,
            "window_size": len(self.window),
            "window_avg_confidence": round(self.window_avg_confidence, 4),
            "frames_as_candidate": self.frames_as_candidate,
            "frames_as_confirmed": self.frames_as_confirmed,
            "consecutive_misses": self.consecutive_misses,
            "total_hits": self.total_hits,
            "total_frames": self.total_frames,
            "first_seen_frame": self.first_seen_frame,
            "last_seen_frame": self.last_seen_frame,
            "last_confidence": round(self.last_confidence, 4),
            "confirmed_at_frame": self.confirmed_at_frame,
        }


@dataclass
class VerificationResult:
    """
    Output of the temporal verifier for a single frame.

    Consumed by downstream modules (risk scoring, incident creation).
    """

    frame_number: int
    timestamp: datetime

    # Categorized threats
    confirmed_threats: List[VerifiedThreat]   # State == CONFIRMED (fire alerts)
    candidate_threats: List[VerifiedThreat]   # State == CANDIDATE (watching)
    new_confirmations: List[VerifiedThreat]   # Just transitioned to CONFIRMED this frame
    resolved_threats: List[VerifiedThreat]    # Just transitioned to RESOLVED this frame
    all_threats: List[VerifiedThreat]         # Every tracked threat (all states)

    @property
    def has_confirmed_threats(self) -> bool:
        return len(self.confirmed_threats) > 0

    @property
    def has_new_confirmations(self) -> bool:
        """Whether any threat was newly confirmed THIS frame (trigger alert)."""
        return len(self.new_confirmations) > 0

    def to_dict(self) -> dict:
        return {
            "frame_number": self.frame_number,
            "timestamp": self.timestamp.isoformat(),
            "confirmed_threats": [t.to_dict() for t in self.confirmed_threats],
            "candidate_threats": [t.to_dict() for t in self.candidate_threats],
            "new_confirmations": [t.to_dict() for t in self.new_confirmations],
            "resolved_threats": [t.to_dict() for t in self.resolved_threats],
            "total_tracked": len(self.all_threats),
        }
