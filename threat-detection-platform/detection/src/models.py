"""
Detection Data Models

Defines the data structures for detection results.
These are the public interface types that downstream modules consume.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple


@dataclass
class BoundingBox:
    """Normalized bounding box coordinates (0.0 - 1.0 relative to frame size)."""

    x1: float  # Top-left X
    y1: float  # Top-left Y
    x2: float  # Bottom-right X
    y2: float  # Bottom-right Y

    @property
    def width(self) -> float:
        """Box width (normalized)."""
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        """Box height (normalized)."""
        return self.y2 - self.y1

    @property
    def center(self) -> Tuple[float, float]:
        """Center point (cx, cy) normalized."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        """Box area (normalized)."""
        return self.width * self.height

    def to_pixel_coords(self, frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
        """Convert normalized coords to pixel coordinates."""
        return (
            int(self.x1 * frame_width),
            int(self.y1 * frame_height),
            int(self.x2 * frame_width),
            int(self.y2 * frame_height),
        )

    def is_valid(self) -> bool:
        """Check if bounding box coordinates are valid."""
        return (
            0.0 <= self.x1 < self.x2 <= 1.0
            and 0.0 <= self.y1 < self.y2 <= 1.0
        )


@dataclass
class Detection:
    """A single object detection result."""

    class_id: int  # Numeric class ID from model
    class_name: str  # Human-readable class name
    confidence: float  # Detection confidence (0.0 - 1.0)
    bbox: BoundingBox  # Bounding box (normalized)
    is_weapon: bool  # Whether this class is a weapon type

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": {
                "x1": round(self.bbox.x1, 4),
                "y1": round(self.bbox.y1, 4),
                "x2": round(self.bbox.x2, 4),
                "y2": round(self.bbox.y2, 4),
            },
            "is_weapon": self.is_weapon,
        }


@dataclass
class FrameResult:
    """Detection results for a single frame."""

    frame_number: int  # Sequential frame number
    timestamp: datetime  # When the frame was processed
    detections: List[Detection]  # All detections in this frame
    frame_width: int  # Original frame width in pixels
    frame_height: int  # Original frame height in pixels
    inference_time_ms: float  # Time taken for inference in milliseconds
    source: str = ""  # Source identifier (file path, camera ID, etc.)

    @property
    def weapon_detections(self) -> List[Detection]:
        """Return only weapon detections."""
        return [d for d in self.detections if d.is_weapon]

    @property
    def person_detections(self) -> List[Detection]:
        """Return only person detections."""
        return [d for d in self.detections if d.class_name == "person"]

    @property
    def detection_count(self) -> int:
        """Total number of detections."""
        return len(self.detections)

    @property
    def has_weapons(self) -> bool:
        """Whether any weapons were detected."""
        return any(d.is_weapon for d in self.detections)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "frame_number": self.frame_number,
            "timestamp": self.timestamp.isoformat(),
            "detections": [d.to_dict() for d in self.detections],
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "source": self.source,
            "detection_count": self.detection_count,
            "has_weapons": self.has_weapons,
        }


# Weapon class names (configurable, but these are the defaults)
WEAPON_CLASSES = frozenset({"handgun", "rifle", "knife", "gun", "pistol", "weapon"})


def is_weapon_class(class_name: str) -> bool:
    """Determine if a class name represents a weapon."""
    return class_name.lower() in WEAPON_CLASSES
