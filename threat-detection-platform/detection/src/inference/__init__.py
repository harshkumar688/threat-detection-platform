"""
Inference Module

Handles YOLO model loading, frame acquisition, inference execution,
and result visualization.

Public API:
- DetectionEngine: High-level entry point (recommended)
- YOLODetector: Low-level detector for custom pipelines
- ModelLoader: Model management
- FrameSource: Frame acquisition from image/video/webcam
"""

from .detector import YOLODetector, DetectionError
from .engine import DetectionEngine
from .frame_source import FrameSource, FrameSourceError, is_image_file, is_video_file
from .model_loader import ModelLoader, ModelLoadError
from .visualizer import draw_detections, draw_frame_info

__all__ = [
    "DetectionEngine",
    "YOLODetector",
    "ModelLoader",
    "ModelLoadError",
    "DetectionError",
    "FrameSource",
    "FrameSourceError",
    "is_image_file",
    "is_video_file",
    "draw_detections",
    "draw_frame_info",
]
