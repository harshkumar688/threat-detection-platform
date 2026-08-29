"""
Verification Configuration

All verification parameters are configurable via environment variables
or direct instantiation.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VerifierConfig(BaseSettings):
    """Configuration for temporal verification."""

    model_config = SettingsConfigDict(
        env_prefix="VERIFIER_",
        env_file=".env",
        extra="ignore",
    )

    # --- Sliding Window (N out of M) ---
    required_hits: int = Field(
        default=3,
        ge=1,
        description=(
            "N: Minimum number of frames (within the window) where the weapon "
            "must be detected to become a CANDIDATE. Higher = stricter."
        ),
    )
    window_size: int = Field(
        default=5,
        ge=1,
        description=(
            "M: Size of the sliding window in frames. The weapon must appear "
            "in at least 'required_hits' out of 'window_size' recent frames."
        ),
    )

    # --- Confidence ---
    min_confidence: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum single-frame confidence to count as a 'hit' in the window. "
            "Detections below this are treated as misses even if the tracker matched them."
        ),
    )
    min_avg_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum average confidence across hit frames to transition to CANDIDATE. "
            "Prevents low-quality persistent detections from triggering."
        ),
    )

    # --- Confirmation ---
    confirm_frames: int = Field(
        default=3,
        ge=1,
        description=(
            "Number of additional frames a CANDIDATE must sustain before becoming CONFIRMED. "
            "Prevents rapid oscillation from generating alerts."
        ),
    )

    # --- Grace Period ---
    grace_period: int = Field(
        default=5,
        ge=0,
        description=(
            "Number of consecutive missed frames allowed before a CANDIDATE "
            "drops back to NO_THREAT. Handles brief occlusions."
        ),
    )

    # --- Resolution ---
    lost_timeout: int = Field(
        default=30,
        ge=1,
        description=(
            "Number of consecutive missed frames before a CONFIRMED threat "
            "transitions to RESOLVED (threat no longer active)."
        ),
    )
