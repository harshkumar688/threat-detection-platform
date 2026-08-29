"""
Object Tracking Module

Assigns persistent identity (track IDs) to detected objects across frames.
Uses IoU-based association with the Hungarian algorithm.

Key Concepts:
─────────────────────────────────────────────────────────────────
Detection vs Tracking:

  DETECTION is a single-frame operation. The YOLO model sees one frame
  and outputs bounding boxes. It has NO memory — if the same person
  appears in frame 1 and frame 2, detection treats them as two
  independent observations with no link between them.

  TRACKING is a multi-frame operation. It takes the stream of per-frame
  detections and answers: "Is the handgun in frame 47 the SAME handgun
  that was in frame 46?" It assigns a stable TRACK ID that persists
  across frames so downstream modules know they're looking at the same
  physical object over time.

  TRACK ID is a unique integer assigned when an object first appears.
  It stays constant as long as the tracker considers it the same object.
  Example: person enters at frame 10 → gets track_id=5. That person
  keeps track_id=5 through frame 200 until they leave the scene.

  LOST TRACK is a track whose associated object was NOT detected in the
  current frame. The tracker doesn't immediately delete it — the object
  might be temporarily occluded or the detector might have missed it
  for a frame. A lost track accumulates "miss" frames. If it exceeds
  max_age without being matched again, it's removed.

  NEW TRACK is created when a detection cannot be matched to any
  existing track. It means a new object just entered the scene. New
  tracks start with age=0 and must be confirmed (matched for min_hits
  consecutive frames) before being reported as active.
─────────────────────────────────────────────────────────────────

Public API:
    from detection.src.tracking import ObjectTracker, TrackerConfig

    config = TrackerConfig()
    tracker = ObjectTracker(config)

    # Feed detections frame by frame
    tracked = tracker.update(frame_result)
    for t in tracked.active_tracks:
        print(f"Track {t.track_id}: {t.class_name} @ {t.bbox}")
"""

from .config import TrackerConfig
from .tracker import ObjectTracker
from .models import Track, TrackState, TrackedFrame

__all__ = [
    "ObjectTracker",
    "TrackerConfig",
    "Track",
    "TrackState",
    "TrackedFrame",
]
