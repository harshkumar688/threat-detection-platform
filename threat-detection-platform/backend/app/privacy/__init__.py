"""
Privacy-Preserving Processing Module (Backend)

Optional face anonymization applied to evidence snapshots before they are
ever written to storage.

Components:
- FaceDetector: locates face-shaped regions (localization only)
- FaceAnonymizer: blurs/pixelates those regions
- PrivacyConfig / PrivacyMode: environment-driven configuration

Hard boundaries (see config.py and face_detector.py docstrings for detail):
- No face recognition, embeddings, or identity matching of any kind.
- No per-person tracking or biometric signature is stored.
- Detection is a best-effort heuristic (Haar cascade), not a guarantee
  every face in every frame will be found.

This module never collects personal data beyond what is already present
in a video frame; it exists to reduce, not increase, the amount of
identifiable personal data that continues downstream once enabled.
"""

from .anonymizer import FaceAnonymizer
from .config import PrivacyConfig, PrivacyMode, get_privacy_config
from .face_detector import FaceBox, FaceDetector, FaceDetectorError

__all__ = [
    "FaceAnonymizer",
    "PrivacyConfig",
    "PrivacyMode",
    "get_privacy_config",
    "FaceBox",
    "FaceDetector",
    "FaceDetectorError",
]
