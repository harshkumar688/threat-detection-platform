"""
Temporal Verifier

Core verification engine. Maintains per-track verification state
and applies the sliding-window algorithm to determine if a weapon
detection is persistent enough to be a real threat.

Algorithm (per weapon track, per frame):
────────────────────────────────────────────────────────────────
1. Update sliding window:
   - If track is active (matched) AND confidence >= min_confidence:
       append (True, confidence) to window
   - Else:
       append (False, 0.0) to window
   - Trim window to max size M

2. Apply state transitions based on current state:

   NO_THREAT:
     IF window_hits >= N AND window_avg_confidence >= min_avg_confidence:
       → CANDIDATE (start confirmation timer)
     ELSE:
       → stay NO_THREAT

   CANDIDATE:
     IF consecutive_misses > grace_period:
       → NO_THREAT (reset)
     ELIF frames_as_candidate >= confirm_frames:
       → CONFIRMED (fire alert!)
     ELSE:
       → stay CANDIDATE (incrementing timer)

   CONFIRMED:
     IF consecutive_misses > lost_timeout:
       → RESOLVED (threat gone)
     ELSE:
       → stay CONFIRMED

   RESOLVED:
     → terminal state (removed from active tracking)
────────────────────────────────────────────────────────────────
"""

from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from ..logger import get_logger
from ..tracking.models import Track, TrackedFrame
from .config import VerifierConfig
from .models import ThreatState, VerifiedThreat, VerificationResult

logger = get_logger(__name__)


class TemporalVerifier:
    """
    Temporal verification engine for weapon tracks.

    Usage:
        config = VerifierConfig(required_hits=3, window_size=5, confirm_frames=3)
        verifier = TemporalVerifier(config)

        for tracked_frame in tracker_output_stream:
            result = verifier.update(tracked_frame)
            if result.has_new_confirmations:
                for threat in result.new_confirmations:
                    create_incident(threat)
    """

    def __init__(self, config: Optional[VerifierConfig] = None):
        """
        Initialize verifier.

        Args:
            config: Verification configuration. Uses defaults if None.
        """
        self.config = config or VerifierConfig()
        self._threats: Dict[int, VerifiedThreat] = {}  # track_id → VerifiedThreat
        self._resolved: List[VerifiedThreat] = []      # Recently resolved (for output)

    def update(self, tracked_frame: TrackedFrame) -> VerificationResult:
        """
        Process a new tracked frame and update all verification states.

        Args:
            tracked_frame: Output from ObjectTracker.update().

        Returns:
            VerificationResult with categorized threats.
        """
        frame_number = tracked_frame.frame_number
        timestamp = tracked_frame.timestamp

        # Collect active weapon track IDs this frame
        active_weapon_ids: Set[int] = set()
        active_tracks_map: Dict[int, Track] = {}

        for track in tracked_frame.all_tracks:
            if track.is_weapon:
                active_tracks_map[track.track_id] = track
                if track.time_since_update == 0:  # Matched this frame
                    active_weapon_ids.add(track.track_id)

        # --- Process each known threat ---
        new_confirmations: List[VerifiedThreat] = []
        newly_resolved: List[VerifiedThreat] = []

        # Update existing threats
        for track_id, threat in list(self._threats.items()):
            track = active_tracks_map.get(track_id)

            # Determine if this track was detected this frame with sufficient confidence
            is_hit = (
                track_id in active_weapon_ids
                and track is not None
                and track.confidence >= self.config.min_confidence
            )
            confidence = track.confidence if (track and is_hit) else 0.0

            # Update sliding window
            threat.window.append((is_hit, confidence))
            if len(threat.window) > self.config.window_size:
                threat.window.popleft()

            threat.total_frames += 1

            if is_hit:
                threat.consecutive_misses = 0
                threat.total_hits += 1
                threat.last_seen_frame = frame_number
                threat.last_confidence = confidence
                if track:
                    threat.bbox = track.bbox
            else:
                threat.consecutive_misses += 1

            # Apply state machine transition
            prev_state = threat.state
            self._transition(threat, frame_number)

            # Detect new confirmations
            if prev_state != ThreatState.CONFIRMED and threat.state == ThreatState.CONFIRMED:
                new_confirmations.append(threat)
                logger.info(
                    "threat_confirmed",
                    track_id=track_id,
                    class_name=threat.class_name,
                    frame=frame_number,
                    total_hits=threat.total_hits,
                    avg_confidence=round(threat.window_avg_confidence, 3),
                )

            # Detect newly resolved
            if prev_state != ThreatState.RESOLVED and threat.state == ThreatState.RESOLVED:
                newly_resolved.append(threat)
                logger.info(
                    "threat_resolved",
                    track_id=track_id,
                    class_name=threat.class_name,
                    frame=frame_number,
                )

        # --- Create new threats for new weapon tracks ---
        for track_id in active_weapon_ids:
            if track_id not in self._threats:
                track = active_tracks_map[track_id]

                # Apply min_confidence filter at creation too
                is_hit = track.confidence >= self.config.min_confidence
                hit_confidence = track.confidence if is_hit else 0.0

                threat = VerifiedThreat(
                    track_id=track_id,
                    class_name=track.class_name,
                    is_weapon=True,
                    state=ThreatState.NO_THREAT,
                    window=deque([(is_hit, hit_confidence)]),
                    consecutive_misses=0 if is_hit else 1,
                    total_hits=1 if is_hit else 0,
                    total_frames=1,
                    first_seen_frame=frame_number,
                    last_seen_frame=frame_number if is_hit else 0,
                    last_confidence=track.confidence,
                    bbox=track.bbox,
                )
                self._threats[track_id] = threat

                # Immediately check if single frame is enough (rare config)
                self._transition(threat, frame_number)

        # --- Handle removed tracks (tracker deleted them) ---
        removed_track_ids = {t.track_id for t in tracked_frame.removed_tracks if t.is_weapon}
        for track_id in removed_track_ids:
            if track_id in self._threats:
                threat = self._threats[track_id]
                if threat.state != ThreatState.RESOLVED:
                    threat.state = ThreatState.RESOLVED
                    threat.resolved_at_frame = frame_number
                    newly_resolved.append(threat)

        # --- Cleanup resolved threats ---
        for threat in newly_resolved:
            if threat.track_id in self._threats:
                del self._threats[threat.track_id]
                self._resolved.append(threat)

        # --- Build output ---
        all_threats = list(self._threats.values())
        confirmed = [t for t in all_threats if t.state == ThreatState.CONFIRMED]
        candidates = [t for t in all_threats if t.state == ThreatState.CANDIDATE]

        return VerificationResult(
            frame_number=frame_number,
            timestamp=timestamp,
            confirmed_threats=confirmed,
            candidate_threats=candidates,
            new_confirmations=new_confirmations,
            resolved_threats=newly_resolved,
            all_threats=all_threats,
        )

    def _transition(self, threat: VerifiedThreat, frame_number: int) -> None:
        """
        Apply state machine transition rules for a single threat.

        Modifies threat.state in place.
        """
        if threat.state == ThreatState.NO_THREAT:
            self._transition_no_threat(threat, frame_number)

        elif threat.state == ThreatState.CANDIDATE:
            self._transition_candidate(threat, frame_number)

        elif threat.state == ThreatState.CONFIRMED:
            self._transition_confirmed(threat, frame_number)

        # RESOLVED is terminal — no transitions out

    def _transition_no_threat(self, threat: VerifiedThreat, frame_number: int) -> None:
        """NO_THREAT → CANDIDATE if N/M threshold met with sufficient confidence."""
        if (
            threat.window_hits >= self.config.required_hits
            and threat.window_avg_confidence >= self.config.min_avg_confidence
        ):
            threat.state = ThreatState.CANDIDATE
            threat.frames_as_candidate = 0
            threat.candidate_since_frame = frame_number
            logger.debug(
                "threat_candidate",
                track_id=threat.track_id,
                frame=frame_number,
                window_hits=threat.window_hits,
                avg_conf=round(threat.window_avg_confidence, 3),
            )

    def _transition_candidate(self, threat: VerifiedThreat, frame_number: int) -> None:
        """
        CANDIDATE transitions:
        - → NO_THREAT if consecutive misses exceed grace period
        - → CONFIRMED if sustained for confirm_frames
        - → stay CANDIDATE otherwise
        """
        # Check if grace period exceeded
        if threat.consecutive_misses > self.config.grace_period:
            threat.state = ThreatState.NO_THREAT
            threat.frames_as_candidate = 0
            threat.candidate_since_frame = None
            logger.debug(
                "candidate_dropped",
                track_id=threat.track_id,
                frame=frame_number,
                misses=threat.consecutive_misses,
            )
            return

        # Increment candidate timer
        threat.frames_as_candidate += 1

        # Check if confirmation threshold reached
        if threat.frames_as_candidate >= self.config.confirm_frames:
            threat.state = ThreatState.CONFIRMED
            threat.confirmed_at_frame = frame_number
            threat.frames_as_confirmed = 0

    def _transition_confirmed(self, threat: VerifiedThreat, frame_number: int) -> None:
        """
        CONFIRMED transitions:
        - → RESOLVED if consecutive misses exceed lost_timeout
        - → stay CONFIRMED otherwise
        """
        threat.frames_as_confirmed += 1

        if threat.consecutive_misses > self.config.lost_timeout:
            threat.state = ThreatState.RESOLVED
            threat.resolved_at_frame = frame_number

    def resolve_threat(self, track_id: int, frame_number: int = 0) -> Optional[VerifiedThreat]:
        """
        Manually resolve a threat (e.g., operator dismisses it).

        Args:
            track_id: Track ID to resolve.
            frame_number: Current frame number.

        Returns:
            The resolved VerifiedThreat, or None if not found.
        """
        threat = self._threats.get(track_id)
        if threat is None:
            return None

        threat.state = ThreatState.RESOLVED
        threat.resolved_at_frame = frame_number
        del self._threats[track_id]
        self._resolved.append(threat)

        logger.info("threat_manually_resolved", track_id=track_id, frame=frame_number)
        return threat

    def reset(self) -> None:
        """Clear all verification state."""
        self._threats.clear()
        self._resolved.clear()
        logger.info("verifier_reset")

    @property
    def active_threat_count(self) -> int:
        """Number of threats currently being tracked (all non-resolved)."""
        return len(self._threats)

    @property
    def confirmed_threat_count(self) -> int:
        """Number of currently confirmed threats."""
        return sum(1 for t in self._threats.values() if t.state == ThreatState.CONFIRMED)

    def get_threat(self, track_id: int) -> Optional[VerifiedThreat]:
        """Look up a threat by track ID."""
        return self._threats.get(track_id)

    def get_info(self) -> dict:
        """Get verifier status."""
        return {
            "active_threats": self.active_threat_count,
            "confirmed_threats": self.confirmed_threat_count,
            "total_resolved": len(self._resolved),
            "config": {
                "required_hits": self.config.required_hits,
                "window_size": self.config.window_size,
                "min_confidence": self.config.min_confidence,
                "min_avg_confidence": self.config.min_avg_confidence,
                "confirm_frames": self.config.confirm_frames,
                "grace_period": self.config.grace_period,
                "lost_timeout": self.config.lost_timeout,
            },
        }
