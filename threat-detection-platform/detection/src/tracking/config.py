"""
Tracker Configuration

All tracking parameters are configurable.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrackerConfig(BaseSettings):
    """Configuration for the object tracker."""

    model_config = SettingsConfigDict(
        env_prefix="TRACKER_",
        env_file=".env",
        extra="ignore",
    )

    # --- Association ---
    iou_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum IoU overlap to associate a detection with an existing track. "
            "Lower values are more permissive (associate more loosely)."
        ),
    )

    # --- Track Lifecycle ---
    max_age: int = Field(
        default=30,
        ge=1,
        description=(
            "Number of consecutive frames a track can go unmatched before deletion. "
            "Higher values tolerate longer occlusions but risk ghost tracks."
        ),
    )
    min_hits: int = Field(
        default=3,
        ge=1,
        description=(
            "Minimum number of consecutive detections required before a track "
            "is considered 'confirmed' and reported as active. Prevents single-frame "
            "false positives from creating tracks."
        ),
    )

    # --- Track ID ---
    initial_track_id: int = Field(
        default=1,
        ge=1,
        description="Starting track ID (increments from here).",
    )
