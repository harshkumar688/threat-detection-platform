"""
Privacy Configuration (Backend)

Controls optional face-anonymization applied to frames at evidence-capture
time, before they are ever written to storage.

Scope and hard boundaries — read before changing defaults:

- This performs face LOCALIZATION only, via OpenCV's pretrained Haar
  cascade frontal-face detector. It answers "is there a face-shaped
  region here?" — never "whose face is this?".
- It does NOT perform face recognition, embeddings, biometric templates,
  or any identity matching/inference. No per-person signature is ever
  computed or stored by this module.
- Haar-cascade detection is a heuristic, not a deep model. It can miss
  non-frontal, poorly lit, occluded, or very small faces, and can
  occasionally flag non-face regions. This is a best-effort privacy
  safeguard, not a certified or guaranteed anonymization mechanism.
- When enabled, anonymization is applied destructively to the frame
  BEFORE it reaches EvidenceStorage — the unblurred frame is never
  written to disk or the database. There is no way to "undo" the blur
  after the fact, by design.

This is a standalone module (not a cross-import from the detection
service) because backend and detection are independently deployable
services with separate dependency sets, matching the rest of this
repository's architecture.
"""

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PrivacyMode(str, Enum):
    """Supported privacy processing modes."""

    OFF = "off"
    """No anonymization applied. Default."""

    FACE_BLUR = "face_blur"
    """Gaussian-blur detected face regions."""

    FACE_PIXELATE = "face_pixelate"
    """Pixelate (mosaic) detected face regions."""


class PrivacyConfig(BaseSettings):
    """Configuration for privacy-preserving evidence capture."""

    model_config = SettingsConfigDict(
        env_prefix="PRIVACY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Mode ---
    mode: PrivacyMode = Field(
        default=PrivacyMode.OFF,
        description="Privacy mode applied to evidence snapshots. OFF, face_blur, or face_pixelate.",
    )

    # --- Blur tuning ---
    blur_kernel_ratio: float = Field(
        default=0.35,
        ge=0.05,
        le=1.0,
        description="Gaussian blur kernel size as a ratio of the face box's shorter side.",
    )

    # --- Pixelation tuning ---
    pixelate_block_size: int = Field(
        default=12,
        ge=2,
        le=64,
        description="Block size (pixels) used when downsampling/upsampling for pixelation.",
    )

    # --- Face detection tuning ---
    detection_scale_factor: float = Field(
        default=1.1,
        gt=1.0,
        le=2.0,
        description="Haar cascade scaleFactor.",
    )
    detection_min_neighbors: int = Field(
        default=5,
        ge=1,
        description="Haar cascade minNeighbors — higher values reduce false positives.",
    )
    detection_min_face_ratio: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Minimum face size as a ratio of frame width.",
    )
    expand_box_ratio: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Expand each detected face box by this ratio before anonymizing (safety margin).",
    )


def get_privacy_config() -> PrivacyConfig:
    """Create and return privacy configuration."""
    return PrivacyConfig()
