"""
Detection Module Configuration

All detection parameters loaded from environment variables or defaults.
"""

from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DetectionConfig(BaseSettings):
    """Configuration for the AI detection module."""

    model_config = SettingsConfigDict(
        env_prefix="DETECTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Model ---
    model_path: str = Field(
        default="yolov8n.pt",
        description="Path to YOLO model weights (.pt file). Can be a local path or Ultralytics model name.",
    )
    device: str = Field(
        default="auto",
        description="Inference device: 'auto', 'cpu', 'cuda', 'cuda:0', etc.",
    )
    input_size: int = Field(
        default=640,
        description="Model input resolution (square). Options: 320, 640, 1280.",
    )

    # --- Detection Thresholds ---
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score to accept a detection.",
    )
    nms_iou_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="IoU threshold for Non-Maximum Suppression.",
    )

    # --- Classes ---
    target_classes: Optional[List[str]] = Field(
        default=None,
        description="Filter to only these class names. None means detect all classes.",
    )

    # --- Video/Webcam ---
    webcam_index: int = Field(
        default=0,
        description="Default webcam device index.",
    )
    max_fps: int = Field(
        default=30,
        ge=1,
        le=120,
        description="Maximum frames per second to process.",
    )

    # --- Visualization ---
    draw_bboxes: bool = Field(
        default=True,
        description="Whether to draw bounding boxes on output frames.",
    )
    bbox_thickness: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Bounding box line thickness in pixels.",
    )
    font_scale: float = Field(
        default=0.6,
        ge=0.1,
        le=3.0,
        description="Font scale for label text.",
    )

    # --- Logging ---
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR.",
    )


def get_detection_config() -> DetectionConfig:
    """Create and return detection configuration."""
    return DetectionConfig()
