"""
Temporal Verification Module

Reduces false alerts by requiring consistent detection evidence
before confirming a threat. Uses a sliding-window approach to
determine if a weapon detection is persistent enough to be real.

State Machine:
    NO_THREAT → CANDIDATE → CONFIRMED → RESOLVED

    - NO_THREAT: Weapon track exists but hasn't met verification threshold
    - CANDIDATE: Met initial N/M threshold, awaiting sustained confirmation
    - CONFIRMED: Verified threat — downstream modules should create an incident
    - RESOLVED: Threat is no longer active (track lost or manually resolved)

Public API:
    from detection.src.verification import TemporalVerifier, VerifierConfig

    config = VerifierConfig(required_hits=3, window_size=5)
    verifier = TemporalVerifier(config)

    # Each frame, feed tracked weapons:
    verified_threats = verifier.update(tracked_frame)
    for threat in verified_threats:
        if threat.state == ThreatState.CONFIRMED:
            # Fire alert!
"""

from .config import VerifierConfig
from .models import ThreatState, VerifiedThreat, VerificationResult
from .verifier import TemporalVerifier

__all__ = [
    "TemporalVerifier",
    "VerifierConfig",
    "ThreatState",
    "VerifiedThreat",
    "VerificationResult",
]
