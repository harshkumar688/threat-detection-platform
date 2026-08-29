"""
Detection-to-Track Association

Uses IoU (Intersection over Union) as the cost metric and
the Hungarian algorithm (scipy.optimize.linear_sum_assignment)
to find the optimal one-to-one matching between existing tracks
and new detections.
"""

from typing import List, Tuple

import numpy as np

from ..models import BoundingBox


def compute_iou(box_a: BoundingBox, box_b: BoundingBox) -> float:
    """
    Compute IoU between two bounding boxes.

    Both boxes use normalized coordinates (0-1).

    Args:
        box_a: First bounding box.
        box_b: Second bounding box.

    Returns:
        IoU value between 0.0 and 1.0.
    """
    # Intersection
    x1 = max(box_a.x1, box_b.x1)
    y1 = max(box_a.y1, box_b.y1)
    x2 = min(box_a.x2, box_b.x2)
    y2 = min(box_a.y2, box_b.y2)

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)

    if intersection == 0.0:
        return 0.0

    # Union
    area_a = box_a.area
    area_b = box_b.area
    union = area_a + area_b - intersection

    if union <= 0.0:
        return 0.0

    return intersection / union


def compute_iou_matrix(
    track_boxes: List[BoundingBox],
    detection_boxes: List[BoundingBox],
) -> np.ndarray:
    """
    Compute IoU matrix between all tracks and all detections.

    Args:
        track_boxes: List of bounding boxes from existing tracks.
        detection_boxes: List of bounding boxes from current frame detections.

    Returns:
        IoU matrix of shape (num_tracks, num_detections).
        iou_matrix[i][j] = IoU between track i and detection j.
    """
    num_tracks = len(track_boxes)
    num_dets = len(detection_boxes)

    if num_tracks == 0 or num_dets == 0:
        return np.empty((num_tracks, num_dets))

    iou_matrix = np.zeros((num_tracks, num_dets))

    for i, track_box in enumerate(track_boxes):
        for j, det_box in enumerate(detection_boxes):
            iou_matrix[i, j] = compute_iou(track_box, det_box)

    return iou_matrix


def associate_detections_to_tracks(
    iou_matrix: np.ndarray,
    iou_threshold: float,
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """
    Associate detections to tracks using the Hungarian algorithm.

    Args:
        iou_matrix: IoU matrix (num_tracks x num_detections).
        iou_threshold: Minimum IoU to accept a match.

    Returns:
        Tuple of:
        - matches: List of (track_index, detection_index) pairs
        - unmatched_tracks: List of track indices with no match
        - unmatched_detections: List of detection indices with no match
    """
    num_tracks, num_dets = iou_matrix.shape

    if num_tracks == 0:
        return [], [], list(range(num_dets))

    if num_dets == 0:
        return [], list(range(num_tracks)), []

    # Use scipy's linear_sum_assignment (Hungarian algorithm)
    # It minimizes cost, so we use (1 - IoU) as cost
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        # Fallback to greedy matching if scipy unavailable
        return _greedy_match(iou_matrix, iou_threshold)

    cost_matrix = 1.0 - iou_matrix
    track_indices, det_indices = linear_sum_assignment(cost_matrix)

    # Filter matches that don't meet IoU threshold
    matches = []
    unmatched_tracks = set(range(num_tracks))
    unmatched_detections = set(range(num_dets))

    for t_idx, d_idx in zip(track_indices, det_indices):
        if iou_matrix[t_idx, d_idx] >= iou_threshold:
            matches.append((t_idx, d_idx))
            unmatched_tracks.discard(t_idx)
            unmatched_detections.discard(d_idx)

    return matches, sorted(unmatched_tracks), sorted(unmatched_detections)


def _greedy_match(
    iou_matrix: np.ndarray,
    iou_threshold: float,
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """
    Greedy matching fallback (when scipy is not available).

    Repeatedly selects the highest IoU pair until no more valid pairs exist.
    Not optimal but simple and deterministic.
    """
    num_tracks, num_dets = iou_matrix.shape
    matched_tracks = set()
    matched_dets = set()
    matches = []

    # Flatten and sort by IoU descending
    flat_indices = np.argsort(-iou_matrix.ravel())

    for flat_idx in flat_indices:
        t_idx = flat_idx // num_dets
        d_idx = flat_idx % num_dets

        if t_idx in matched_tracks or d_idx in matched_dets:
            continue

        iou_val = iou_matrix[t_idx, d_idx]
        if iou_val < iou_threshold:
            break  # All remaining are below threshold

        matches.append((t_idx, d_idx))
        matched_tracks.add(t_idx)
        matched_dets.add(d_idx)

    unmatched_tracks = sorted(set(range(num_tracks)) - matched_tracks)
    unmatched_detections = sorted(set(range(num_dets)) - matched_dets)

    return matches, unmatched_tracks, unmatched_detections
