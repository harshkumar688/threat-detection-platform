"""
Scoring Configuration

All scoring parameters configurable via environment or direct instantiation.
Nothing is hard-coded — every threshold, weight, and lookup is configurable.
"""

from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringConfig(BaseSettings):
    """Configuration for the risk scoring engine."""

    model_config = SettingsConfigDict(
        env_prefix="SCORING_",
        env_file=".env",
        extra="ignore",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Factor Weights (must sum to 1.0)
    # Each weight determines how much that factor contributes to the total score.
    # ─────────────────────────────────────────────────────────────────────────
    weight_weapon_severity: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Weight for weapon class severity factor.",
    )
    weight_confidence: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Weight for detection confidence factor.",
    )
    weight_persistence: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Weight for persistence (frames visible) factor.",
    )
    weight_weapon_count: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Weight for number of weapons detected.",
    )
    weight_location: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Weight for location sensitivity factor.",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Weapon Severity Lookup (class_name → severity score 0-100)
    # ─────────────────────────────────────────────────────────────────────────
    weapon_severity_scores: Dict[str, float] = Field(
        default={
            "rifle": 100.0,
            "handgun": 85.0,
            "gun": 85.0,
            "pistol": 85.0,
            "knife": 50.0,
            "weapon": 75.0,
        },
        description="Severity score (0-100) for each weapon class name.",
    )
    default_weapon_severity: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Severity score for weapon classes not in the lookup table.",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Persistence Normalization
    # ─────────────────────────────────────────────────────────────────────────
    persistence_max_frames: int = Field(
        default=15,
        ge=1,
        description=(
            "Number of confirmed frames at which persistence score reaches 100. "
            "Frames beyond this don't increase the score further."
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Weapon Count Normalization
    # ─────────────────────────────────────────────────────────────────────────
    weapon_count_max: int = Field(
        default=3,
        ge=1,
        description=(
            "Number of simultaneous weapons at which count score reaches 100. "
            "Beyond this, score is capped at 100."
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Location Multipliers
    # ─────────────────────────────────────────────────────────────────────────
    location_multipliers: Dict[str, float] = Field(
        default={
            "default": 1.0,
        },
        description=(
            "Per-location (or per-camera) multiplier. "
            "Values > 1.0 increase urgency for sensitive zones. "
            "Example: {'lobby': 1.0, 'server_room': 1.5, 'parking': 0.8}"
        ),
    )
    default_location_multiplier: float = Field(
        default=1.0,
        ge=0.1,
        le=3.0,
        description="Multiplier for locations not in the lookup table.",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Risk Level Thresholds
    # ─────────────────────────────────────────────────────────────────────────
    threshold_low_max: float = Field(
        default=30.0,
        ge=0.0,
        le=100.0,
        description="Maximum score for LOW risk level.",
    )
    threshold_medium_max: float = Field(
        default=55.0,
        ge=0.0,
        le=100.0,
        description="Maximum score for MEDIUM risk level.",
    )
    threshold_high_max: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Maximum score for HIGH risk level. Above this is CRITICAL.",
    )
