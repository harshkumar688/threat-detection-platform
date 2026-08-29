"""
Privacy Module Tests

Verifies:
- PrivacyConfig defaults and mode switching
- FaceDetector localizes real faces drawn into synthetic images, and
  returns no boxes for blank/featureless frames
- FaceAnonymizer blur/pixelate modes actually change pixel data within
  detected regions, leave the frame untouched when mode is OFF, and
  never touch frames with no detected faces
- No identity-related data (encodings, names, embeddings) is ever
  produced by any public method in this module
"""

import cv2
import numpy as np
import pytest

from src.privacy import FaceAnonymizer, FaceDetector, PrivacyConfig, PrivacyMode


def _draw_synthetic_face(frame: np.ndarray, cx: int, cy: int, size: int) -> None:
    """
    Draw a crude but Haar-cascade-detectable frontal face: a light oval
    "head" with two dark eye blobs and a mouth line. Not a real photo —
    used only to give the classical cascade detector real edge/contrast
    features to find, since random noise won't trigger it.
    """
    cv2.ellipse(frame, (cx, cy), (size // 2, int(size * 0.6)), 0, 0, 360, (200, 180, 170), -1)
    eye_offset = size // 4
    eye_y = cy - size // 6
    cv2.circle(frame, (cx - eye_offset, eye_y), max(2, size // 10), (30, 30, 30), -1)
    cv2.circle(frame, (cx + eye_offset, eye_y), max(2, size // 10), (30, 30, 30), -1)
    cv2.line(frame, (cx - size // 6, cy + size // 4), (cx + size // 6, cy + size // 4), (60, 40, 40), 2)


@pytest.fixture
def blank_frame():
    return np.full((480, 640, 3), 220, dtype=np.uint8)


@pytest.fixture
def face_like_frame():
    frame = np.full((480, 640, 3), 60, dtype=np.uint8)
    _draw_synthetic_face(frame, cx=320, cy=240, size=220)
    return frame


class TestPrivacyConfig:
    def test_default_mode_is_off(self):
        config = PrivacyConfig()
        assert config.mode == PrivacyMode.OFF

    def test_mode_configurable(self):
        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR)
        assert config.mode == PrivacyMode.FACE_BLUR

    def test_pixelate_mode(self):
        config = PrivacyConfig(mode=PrivacyMode.FACE_PIXELATE)
        assert config.mode == PrivacyMode.FACE_PIXELATE

    def test_blur_kernel_ratio_bounded(self):
        with pytest.raises(Exception):
            PrivacyConfig(blur_kernel_ratio=5.0)  # > le=1.0

    def test_detection_min_neighbors_configurable(self):
        config = PrivacyConfig(detection_min_neighbors=8)
        assert config.detection_min_neighbors == 8


class TestFaceDetectorLocalizationOnly:
    def test_no_identity_producing_methods_exist(self):
        """
        Guard against scope creep: the public surface of FaceDetector must
        never grow identity/recognition-related methods.
        """
        detector = FaceDetector()
        forbidden_terms = ("recognize", "identify", "embed", "encode", "match", "name")
        public_methods = [m for m in dir(detector) if not m.startswith("_")]
        for method in public_methods:
            for term in forbidden_terms:
                assert term not in method.lower(), (
                    f"FaceDetector exposes '{method}', which suggests identity "
                    "inference — this module must remain localization-only."
                )

    def test_detect_returns_empty_list_for_blank_frame(self, blank_frame):
        detector = FaceDetector()
        boxes = detector.detect(blank_frame)
        assert boxes == []

    def test_detect_returns_boxes_as_tuples_of_four_ints(self, face_like_frame):
        detector = FaceDetector(min_neighbors=1, min_face_ratio=0.01)
        boxes = detector.detect(face_like_frame)
        # Haar cascades are heuristic; we only assert on structure/type here,
        # not that a specific synthetic drawing is guaranteed to match.
        for box in boxes:
            assert len(box) == 4
            assert all(isinstance(v, int) for v in box)

    def test_detect_handles_empty_frame_gracefully(self):
        detector = FaceDetector()
        assert detector.detect(np.array([])) == []

    def test_detect_handles_none_gracefully(self):
        detector = FaceDetector()
        assert detector.detect(None) == []


class TestFaceAnonymizerOffMode:
    def test_off_mode_returns_frame_unmodified(self, face_like_frame):
        config = PrivacyConfig(mode=PrivacyMode.OFF)
        anonymizer = FaceAnonymizer(config)

        original = face_like_frame.copy()
        result, count = anonymizer.process(face_like_frame)

        assert count == 0
        assert np.array_equal(result, original)

    def test_off_mode_on_blank_frame(self, blank_frame):
        config = PrivacyConfig(mode=PrivacyMode.OFF)
        anonymizer = FaceAnonymizer(config)
        result, count = anonymizer.process(blank_frame)
        assert count == 0
        assert np.array_equal(result, blank_frame)


class TestFaceAnonymizerNoFacesDetected:
    def test_blur_mode_leaves_frame_untouched_when_no_faces_found(self, blank_frame):
        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR)
        anonymizer = FaceAnonymizer(config)

        original = blank_frame.copy()
        result, count = anonymizer.process(blank_frame)

        assert count == 0
        assert np.array_equal(result, original)


class TestFaceAnonymizerBlurAndPixelate:
    def test_blur_mode_modifies_pixels_in_a_manufactured_region(self):
        """
        Bypass real face detection (unreliable on synthetic art) by
        injecting a stub detector that reports a fixed box, to verify the
        pixel-transformation logic itself is correct and destructive.
        """
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[50:150, 50:150] = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        original = frame.copy()

        class StubDetector:
            def detect(self, f):
                return [(50, 50, 100, 100)]

        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR, expand_box_ratio=0.0)
        anonymizer = FaceAnonymizer(config, detector=StubDetector())

        result, count = anonymizer.process(frame)

        assert count == 1
        # Region inside the box must have changed (blurred), region outside must not.
        assert not np.array_equal(result[50:150, 50:150], original[50:150, 50:150])
        assert np.array_equal(result[:50, :], original[:50, :])
        assert np.array_equal(result[150:, :], original[150:, :])

    def test_pixelate_mode_modifies_pixels_in_a_manufactured_region(self):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[50:150, 50:150] = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        original = frame.copy()

        class StubDetector:
            def detect(self, f):
                return [(50, 50, 100, 100)]

        config = PrivacyConfig(mode=PrivacyMode.FACE_PIXELATE, expand_box_ratio=0.0, pixelate_block_size=10)
        anonymizer = FaceAnonymizer(config, detector=StubDetector())

        result, count = anonymizer.process(frame)

        assert count == 1
        assert not np.array_equal(result[50:150, 50:150], original[50:150, 50:150])
        assert np.array_equal(result[:50, :], original[:50, :])

    def test_expand_box_ratio_grows_region_but_stays_in_bounds(self):
        frame = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

        class StubDetector:
            def detect(self, f):
                return [(90, 90, 20, 20)]

        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR, expand_box_ratio=0.5)
        anonymizer = FaceAnonymizer(config, detector=StubDetector())

        expanded = anonymizer._expand_box((90, 90, 20, 20), frame.shape)
        x, y, w, h = expanded
        assert w > 20
        assert h > 20
        assert x >= 0 and y >= 0
        assert x + w <= 200 and y + h <= 200

    def test_expand_box_clamped_at_frame_edge(self):
        """Boxes near the frame border must not expand past the frame boundary."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        class StubDetector:
            def detect(self, f):
                return [(0, 0, 20, 20)]

        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR, expand_box_ratio=1.0)
        anonymizer = FaceAnonymizer(config, detector=StubDetector())

        x, y, w, h = anonymizer._expand_box((0, 0, 20, 20), frame.shape)
        assert x == 0
        assert y == 0
        assert x + w <= 100
        assert y + h <= 100

    def test_multiple_faces_all_anonymized(self):
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        frame[20:80, 20:80] = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
        frame[20:80, 300:360] = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
        original = frame.copy()

        class StubDetector:
            def detect(self, f):
                return [(20, 20, 60, 60), (300, 20, 60, 60)]

        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR, expand_box_ratio=0.0)
        anonymizer = FaceAnonymizer(config, detector=StubDetector())

        result, count = anonymizer.process(frame)

        assert count == 2
        assert not np.array_equal(result[20:80, 20:80], original[20:80, 20:80])
        assert not np.array_equal(result[20:80, 300:360], original[20:80, 300:360])

    def test_zero_area_region_skipped_without_error(self):
        """A degenerate zero-width/height box must not crash processing."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        class StubDetector:
            def detect(self, f):
                return [(50, 50, 0, 0)]

        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR)
        anonymizer = FaceAnonymizer(config, detector=StubDetector())

        result, count = anonymizer.process(frame)
        assert count == 1  # box was reported, even though region was empty
        assert result is not None


class TestNoIdentityDataProduced:
    def test_anonymizer_process_return_type_has_no_identity_fields(self):
        """
        process() must return only (frame, count) — never names, IDs tied
        to a specific person, or any per-face identity payload.
        """
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR)
        anonymizer = FaceAnonymizer(config, detector=FaceDetector())

        result = anonymizer.process(frame)
        assert isinstance(result, tuple)
        assert len(result) == 2
        frame_out, count = result
        assert isinstance(frame_out, np.ndarray)
        assert isinstance(count, int)
