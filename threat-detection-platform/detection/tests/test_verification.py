"""
Unit tests for the temporal verification module.

Tests the state machine transitions:
    NO_THREAT → CANDIDATE → CONFIRMED → RESOLVED

All tests use synthetic data — no YOLO model needed.
"""

import pytest
from collections import deque
from datetime import datetime, timezone

from src.models import BoundingBox, Detection, FrameResult
from src.tracking.models import Track, TrackedFrame, TrackState
from src.verification import TemporalVerifier, VerifierConfig, ThreatState, VerifiedThreat


# =============================================================================
# Helpers
# =============================================================================

def make_weapon_track(
    track_id: int = 1,
    confidence: float = 0.8,
    time_since_update: int = 0,
    state: TrackState = TrackState.CONFIRMED,
) -> Track:
    """Create a weapon track for testing."""
    return Track(
        track_id=track_id,
        class_name="handgun",
        class_id=0,
        is_weapon=True,
        bbox=BoundingBox(x1=0.3, y1=0.3, x2=0.6, y2=0.7),
        confidence=confidence,
        state=state,
        hits=5,
        age=10,
        time_since_update=time_since_update,
        first_seen_frame=1,
        last_seen_frame=10,
        confidence_sum=4.0,
    )


def make_tracked_frame(
    tracks: list,
    frame_number: int = 1,
    removed: list = None,
) -> TrackedFrame:
    """Create a TrackedFrame for testing."""
    active = [t for t in tracks if t.time_since_update == 0]
    lost = [t for t in tracks if t.time_since_update > 0]
    return TrackedFrame(
        frame_number=frame_number,
        timestamp=datetime.now(timezone.utc),
        active_tracks=active,
        lost_tracks=lost,
        new_tracks=[],
        removed_tracks=removed or [],
        all_tracks=tracks,
    )


def feed_frames(verifier, track_id=1, num_frames=5, confidence=0.8, present=True):
    """Feed multiple frames to the verifier with a weapon track present or absent."""
    results = []
    for i in range(1, num_frames + 1):
        if present:
            track = make_weapon_track(track_id=track_id, confidence=confidence, time_since_update=0)
        else:
            track = make_weapon_track(track_id=track_id, confidence=confidence, time_since_update=i)
        frame = make_tracked_frame([track], frame_number=i)
        results.append(verifier.update(frame))
    return results


# =============================================================================
# State Machine Tests
# =============================================================================

class TestNoThreatState:
    """Tests for the NO_THREAT state."""

    def test_starts_as_no_threat(self):
        config = VerifierConfig(required_hits=3, window_size=5)
        verifier = TemporalVerifier(config)

        track = make_weapon_track(confidence=0.8)
        frame = make_tracked_frame([track], frame_number=1)
        result = verifier.update(frame)

        # First frame — not enough hits yet
        threat = verifier.get_threat(1)
        assert threat is not None
        assert threat.state == ThreatState.NO_THREAT

    def test_stays_no_threat_insufficient_hits(self):
        config = VerifierConfig(required_hits=3, window_size=5, confirm_frames=1)
        verifier = TemporalVerifier(config)

        # Only 2 hits in 5 frames (need 3)
        for i in range(1, 6):
            present = (i <= 2)  # Only first 2 frames have the weapon
            if present:
                track = make_weapon_track(confidence=0.8, time_since_update=0)
            else:
                track = make_weapon_track(confidence=0.8, time_since_update=i - 2)
            frame = make_tracked_frame([track], frame_number=i)
            verifier.update(frame)

        threat = verifier.get_threat(1)
        assert threat.state == ThreatState.NO_THREAT

    def test_stays_no_threat_low_confidence(self):
        """Even with enough hits, if avg confidence too low, stays NO_THREAT."""
        config = VerifierConfig(
            required_hits=3, window_size=5,
            min_confidence=0.3, min_avg_confidence=0.7
        )
        verifier = TemporalVerifier(config)

        # 5 hits but all at low confidence (0.4)
        feed_frames(verifier, num_frames=5, confidence=0.4, present=True)

        threat = verifier.get_threat(1)
        # avg confidence = 0.4 < min_avg_confidence (0.7) → NO_THREAT
        assert threat.state == ThreatState.NO_THREAT


class TestCandidateState:
    """Tests for the CANDIDATE state."""

    def test_transitions_to_candidate(self):
        config = VerifierConfig(
            required_hits=3, window_size=5,
            min_avg_confidence=0.5, confirm_frames=5
        )
        verifier = TemporalVerifier(config)

        # Feed 3 frames with weapon (meets N=3 in M=5)
        feed_frames(verifier, num_frames=3, confidence=0.8)

        threat = verifier.get_threat(1)
        assert threat.state == ThreatState.CANDIDATE

    def test_candidate_drops_on_grace_exceeded(self):
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=10, grace_period=3,
            min_avg_confidence=0.3,
        )
        verifier = TemporalVerifier(config)

        # Get to CANDIDATE
        feed_frames(verifier, num_frames=2, confidence=0.8)
        threat = verifier.get_threat(1)
        assert threat.state == ThreatState.CANDIDATE

        # Now miss for grace_period + 1 frames → drops back
        feed_frames(verifier, num_frames=4, confidence=0.8, present=False)
        threat = verifier.get_threat(1)
        assert threat.state == ThreatState.NO_THREAT

    def test_candidate_tolerates_misses_within_grace(self):
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=10, grace_period=5,
            min_avg_confidence=0.3,
        )
        verifier = TemporalVerifier(config)

        # Get to CANDIDATE
        feed_frames(verifier, num_frames=2, confidence=0.8)
        assert verifier.get_threat(1).state == ThreatState.CANDIDATE

        # Miss for 3 frames (within grace_period=5)
        feed_frames(verifier, num_frames=3, confidence=0.8, present=False)
        # Should still be CANDIDATE
        assert verifier.get_threat(1).state == ThreatState.CANDIDATE


class TestConfirmedState:
    """Tests for the CONFIRMED state."""

    def test_transitions_to_confirmed(self):
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=3, grace_period=10,
            min_avg_confidence=0.3,
        )
        verifier = TemporalVerifier(config)

        # Feed enough frames: 2 to become CANDIDATE + 3 confirm_frames
        results = feed_frames(verifier, num_frames=6, confidence=0.8)

        threat = verifier.get_threat(1)
        assert threat.state == ThreatState.CONFIRMED

    def test_new_confirmations_reported(self):
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=2, grace_period=10,
            min_avg_confidence=0.3,
        )
        verifier = TemporalVerifier(config)

        results = feed_frames(verifier, num_frames=5, confidence=0.8)

        # Find the frame where confirmation happened
        confirmations = [r for r in results if r.has_new_confirmations]
        assert len(confirmations) == 1
        assert confirmations[0].new_confirmations[0].track_id == 1

    def test_confirmed_stays_confirmed_with_hits(self):
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=2, grace_period=10,
            min_avg_confidence=0.3, lost_timeout=30,
        )
        verifier = TemporalVerifier(config)

        # Get to CONFIRMED
        feed_frames(verifier, num_frames=5, confidence=0.8)
        assert verifier.get_threat(1).state == ThreatState.CONFIRMED

        # Continue feeding — stays confirmed
        feed_frames(verifier, num_frames=10, confidence=0.8)
        assert verifier.get_threat(1).state == ThreatState.CONFIRMED


class TestResolvedState:
    """Tests for the RESOLVED state."""

    def test_confirmed_resolves_after_lost_timeout(self):
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=2, grace_period=10,
            min_avg_confidence=0.3, lost_timeout=5,
        )
        verifier = TemporalVerifier(config)

        # Get to CONFIRMED
        feed_frames(verifier, num_frames=5, confidence=0.8)
        assert verifier.get_threat(1).state == ThreatState.CONFIRMED

        # Miss for lost_timeout + 1 frames
        results = feed_frames(verifier, num_frames=7, confidence=0.8, present=False)

        # Threat should be resolved and removed
        assert verifier.get_threat(1) is None

        # Check that resolved was reported
        resolved_results = [r for r in results if r.resolved_threats]
        assert len(resolved_results) > 0

    def test_manual_resolve(self):
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=2, min_avg_confidence=0.3,
        )
        verifier = TemporalVerifier(config)

        feed_frames(verifier, num_frames=5, confidence=0.8)
        assert verifier.get_threat(1).state == ThreatState.CONFIRMED

        # Manually resolve
        resolved = verifier.resolve_threat(track_id=1, frame_number=10)
        assert resolved is not None
        assert resolved.state == ThreatState.RESOLVED
        assert verifier.get_threat(1) is None

    def test_track_removal_resolves_threat(self):
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=2, min_avg_confidence=0.3,
        )
        verifier = TemporalVerifier(config)

        # Get to CONFIRMED
        feed_frames(verifier, num_frames=5, confidence=0.8)

        # Tracker removes the track
        removed_track = make_weapon_track(track_id=1)
        frame = make_tracked_frame([], frame_number=10, removed=[removed_track])
        result = verifier.update(frame)

        assert verifier.get_threat(1) is None
        assert len(result.resolved_threats) == 1


class TestConfiguration:
    """Tests for configuration impact."""

    def test_strict_config_requires_more_evidence(self):
        """Strict config: needs 4/5 hits + 5 confirm frames."""
        config = VerifierConfig(
            required_hits=4, window_size=5,
            confirm_frames=5, min_avg_confidence=0.7,
        )
        verifier = TemporalVerifier(config)

        # 3 frames isn't enough
        feed_frames(verifier, num_frames=3, confidence=0.8)
        assert verifier.get_threat(1).state == ThreatState.NO_THREAT

        # 4 frames → CANDIDATE (4/5 hits met)
        feed_frames(verifier, num_frames=1, confidence=0.8)
        assert verifier.get_threat(1).state == ThreatState.CANDIDATE

    def test_lenient_config_confirms_quickly(self):
        """Lenient config: 1/1 hit + 1 confirm frame."""
        config = VerifierConfig(
            required_hits=1, window_size=1,
            confirm_frames=1, min_avg_confidence=0.0,
        )
        verifier = TemporalVerifier(config)

        # Frame 1: NO_THREAT → CANDIDATE (hit met) → CONFIRMED (confirm_frames met)
        feed_frames(verifier, num_frames=2, confidence=0.5)
        assert verifier.get_threat(1).state == ThreatState.CONFIRMED

    def test_min_confidence_filters_low_quality(self):
        """Detections below min_confidence are treated as misses."""
        config = VerifierConfig(
            required_hits=3, window_size=5,
            min_confidence=0.6, min_avg_confidence=0.3,
            confirm_frames=1,
        )
        verifier = TemporalVerifier(config)

        # 5 frames at 0.5 confidence (below min_confidence=0.6)
        feed_frames(verifier, num_frames=5, confidence=0.5)
        threat = verifier.get_threat(1)
        assert threat.state == ThreatState.NO_THREAT
        assert threat.window_hits == 0  # All counted as misses


class TestVerifierState:
    """Tests for verifier state inspection."""

    def test_active_threat_count(self):
        config = VerifierConfig(required_hits=1, window_size=1, confirm_frames=1, min_avg_confidence=0.0)
        verifier = TemporalVerifier(config)

        track1 = make_weapon_track(track_id=1, confidence=0.8)
        track2 = make_weapon_track(track_id=2, confidence=0.7)
        frame = make_tracked_frame([track1, track2], frame_number=1)
        verifier.update(frame)

        assert verifier.active_threat_count == 2

    def test_reset_clears_state(self):
        config = VerifierConfig(required_hits=1, window_size=1, confirm_frames=1, min_avg_confidence=0.0)
        verifier = TemporalVerifier(config)

        feed_frames(verifier, num_frames=3, confidence=0.8)
        assert verifier.active_threat_count > 0

        verifier.reset()
        assert verifier.active_threat_count == 0

    def test_get_info(self):
        config = VerifierConfig(required_hits=3, window_size=5, confirm_frames=3)
        verifier = TemporalVerifier(config)

        info = verifier.get_info()
        assert info["config"]["required_hits"] == 3
        assert info["config"]["window_size"] == 5
        assert info["config"]["confirm_frames"] == 3
        assert info["active_threats"] == 0

    def test_threat_to_dict(self):
        config = VerifierConfig(required_hits=2, window_size=5, confirm_frames=2, min_avg_confidence=0.3)
        verifier = TemporalVerifier(config)

        feed_frames(verifier, num_frames=5, confidence=0.8)
        threat = verifier.get_threat(1)
        d = threat.to_dict()

        assert d["track_id"] == 1
        assert d["state"] == "confirmed"
        assert d["class_name"] == "handgun"
        assert d["window_avg_confidence"] > 0
        assert "confirmed_at_frame" in d


class TestIntermittentDetection:
    """Tests for handling intermittent detection loss."""

    def test_intermittent_detection_still_confirms(self):
        """Object detected in 3 out of 5 frames (with gaps) should still reach CANDIDATE."""
        config = VerifierConfig(
            required_hits=3, window_size=5,
            confirm_frames=2, grace_period=5,
            min_avg_confidence=0.3,
        )
        verifier = TemporalVerifier(config)

        # Pattern: hit, miss, hit, miss, hit (3/5 hits)
        pattern = [True, False, True, False, True]
        for i, present in enumerate(pattern, 1):
            if present:
                track = make_weapon_track(confidence=0.8, time_since_update=0)
            else:
                track = make_weapon_track(confidence=0.8, time_since_update=1)
            frame = make_tracked_frame([track], frame_number=i)
            verifier.update(frame)

        threat = verifier.get_threat(1)
        assert threat.state == ThreatState.CANDIDATE

    def test_brief_occlusion_doesnt_reset_candidate(self):
        """A 2-frame gap during CANDIDATE should be tolerated (grace_period=5)."""
        config = VerifierConfig(
            required_hits=2, window_size=5,
            confirm_frames=6, grace_period=5,
            min_avg_confidence=0.3,
        )
        verifier = TemporalVerifier(config)

        # Get to CANDIDATE
        feed_frames(verifier, num_frames=2, confidence=0.8)
        assert verifier.get_threat(1).state == ThreatState.CANDIDATE

        # Brief occlusion (2 frames)
        feed_frames(verifier, num_frames=2, confidence=0.8, present=False)
        assert verifier.get_threat(1).state == ThreatState.CANDIDATE  # Still candidate

        # Resume detection
        feed_frames(verifier, num_frames=4, confidence=0.8, present=True)
        # Should eventually confirm
        assert verifier.get_threat(1).state == ThreatState.CONFIRMED
