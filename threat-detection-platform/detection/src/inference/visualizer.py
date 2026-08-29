"""
Detection Visualizer

Draws bounding boxes, labels, and confidence scores on frames.
Separated from detection logic so it can be toggled on/off.
"""

from typing import Dict, Tuple

import cv2
import numpy as np

from ..models import Detection, FrameResult

# Color palette for different classes (BGR format)
DEFAULT_COLORS: Dict[str, Tuple[int, int, int]] = {
    # Weapons - Red shades
    "handgun": (0, 0, 255),
    "rifle": (0, 0, 200),
    "knife": (0, 50, 255),
    "gun": (0, 0, 255),
    "pistol": (0, 0, 255),
    "weapon": (0, 0, 255),
    # Person - Green
    "person": (0, 255, 0),
    # Default - Blue
    "_default": (255, 150, 0),
}


def get_color_for_class(class_name: str) -> Tuple[int, int, int]:
    """Get BGR color for a class name."""
    return DEFAULT_COLORS.get(class_name.lower(), DEFAULT_COLORS["_default"])


def draw_detections(
    frame: np.ndarray,
    result: FrameResult,
    bbox_thickness: int = 2,
    font_scale: float = 0.6,
    show_confidence: bool = True,
    show_label: bool = True,
) -> np.ndarray:
    """
    Draw bounding boxes and labels on a frame.

    Args:
        frame: BGR image (H, W, 3) - will be modified in place.
        result: FrameResult containing detections to draw.
        bbox_thickness: Line thickness for bounding boxes.
        font_scale: Font scale for text labels.
        show_confidence: Whether to show confidence score.
        show_label: Whether to show class name.

    Returns:
        Annotated frame (same array, modified in place).
    """
    for detection in result.detections:
        _draw_single_detection(
            frame=frame,
            detection=detection,
            frame_width=result.frame_width,
            frame_height=result.frame_height,
            thickness=bbox_thickness,
            font_scale=font_scale,
            show_confidence=show_confidence,
            show_label=show_label,
        )

    return frame


def _draw_single_detection(
    frame: np.ndarray,
    detection: Detection,
    frame_width: int,
    frame_height: int,
    thickness: int = 2,
    font_scale: float = 0.6,
    show_confidence: bool = True,
    show_label: bool = True,
) -> None:
    """Draw a single detection on the frame."""
    # Get pixel coordinates
    x1, y1, x2, y2 = detection.bbox.to_pixel_coords(frame_width, frame_height)
    color = get_color_for_class(detection.class_name)

    # Draw bounding box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    # Build label text
    label_parts = []
    if show_label:
        label_parts.append(detection.class_name)
    if show_confidence:
        label_parts.append(f"{detection.confidence:.2f}")

    if label_parts:
        label = " ".join(label_parts)

        # Draw label background
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
        )
        label_y1 = max(y1 - text_height - baseline - 4, 0)
        label_y2 = y1

        cv2.rectangle(
            frame,
            (x1, label_y1),
            (x1 + text_width + 4, label_y2),
            color,
            -1,  # Filled
        )

        # Draw text
        cv2.putText(
            frame,
            label,
            (x1 + 2, label_y2 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),  # White text
            1,
            cv2.LINE_AA,
        )


def draw_frame_info(
    frame: np.ndarray,
    result: FrameResult,
    font_scale: float = 0.5,
) -> np.ndarray:
    """
    Draw frame metadata (frame number, FPS, detection count) overlay.

    Args:
        frame: BGR image to annotate.
        result: FrameResult with metadata.
        font_scale: Font scale for info text.

    Returns:
        Annotated frame.
    """
    info_lines = [
        f"Frame: {result.frame_number}",
        f"Detections: {result.detection_count}",
        f"Inference: {result.inference_time_ms:.1f}ms",
    ]

    if result.has_weapons:
        info_lines.append(f"WEAPONS: {len(result.weapon_detections)}")

    y_offset = 20
    for line in info_lines:
        color = (0, 0, 255) if "WEAPONS" in line else (200, 200, 200)
        cv2.putText(
            frame, line,
            (10, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color, 1, cv2.LINE_AA,
        )
        y_offset += 22

    return frame
