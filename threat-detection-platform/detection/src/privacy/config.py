"""
Privacy Configuration

Controls optional face-anonymization applied to frames before they are
displayed, transmitted downstream, or persisted as evidence.

Scope and hard boundaries — read before wiring this into a pipeline:

- This module performs face LOCALIZATION only, using a classical,
  non-learned-identity Haar-cascade detector (OpenCV's pretrained
  "frontal face" cascade). It answers only "is there a face-shaped region
  here?" — it never asks or answers "whose face is this?".
- It does NOT perform face recognition, face embedding/encoding, face
  matching against a database, or any other form of identity inference.
  No per-person signature is ever computed or stored.
- Haar-cascade detection is a coarse heuristic, not a deep model. It can
  miss faces (false negatives) at extreme angles, in poor lighting, when
  partially occluded, or when small/far from the camera — and it can
  occasionally flag non-face regions (false positives). Treat this as
  best-effort privacy hardening, not a guaranteed or legally-certified
  anonymization mechanism.
- Blurring/pixelation is applied destructively to the returned frame.
  Callers that only keep the processed output (as evidence capture does)
  never retain a hidden unblurred copy.

Configuration is environment-driven so operators can enable/disable and
tune anonymization without code changes.
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
    """Configuration for the privacy-preserving processing module."""

    model_config = SettingsConfigDict(
        env_prefix="PRIVACY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Mode ---
    mode: PrivacyMode = Field(
        default=PrivacyMode.OFF,
        description="Global default privacy mode. OFF, face_blur, or face_pixelate.",
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

    # --- Face detection tuning (Haar cascade parameters) ---
    detection_scale_factor: float = Field(
        default=1.1,
        gt=1.0,
        le=2.0,
        description="Haar cascade scaleFactor — how much the image size is reduced at each scale.",
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
        description="Minimum face size as a ratio of frame width; filters out tiny false positives.",
    )
    expand_box_ratio: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Expand each detected face box by this ratio on every side before anonymizing, as a safety margin.",
    )


def get_privacy_config() -> PrivacyConfig:
    """Create and return privacy configuration."""
    return PrivacyConfig()
