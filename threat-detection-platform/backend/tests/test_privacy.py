"""
Backend Privacy Module Tests

Verifies:
- PrivacyConfig defaults and mode switching
- FaceDetector localization behavior (never raises for "no face found")
- FaceAnonymizer blur/pixelate actually change pixel data, leave frames
  untouched when mode is OFF or no faces are found
- EvidenceService applies anonymization BEFORE storage.save_snapshot(),
  so the persisted file already reflects the blur/pixelation — there is
  no unblurred copy anywhere once privacy mode is enabled
- EvidenceRecord tracks which privacy mode was applied and how many
  faces were anonymized, for transparency
- No identity-related data is ever produced by this module's public API
"""

from uuid import uuid4

import numpy as np
import pytest

from app.evidence import EvidenceConfig, EvidenceService, EvidenceStorage, InMemoryEvidenceRepository
from app.privacy import FaceAnonymizer, FaceDetector, PrivacyConfig, PrivacyMode


@pytest.fixture
def evidence_config(tmp_path):
    return EvidenceConfig(
        storage_path=str(tmp_path / "evidence_store"),
        retention_days=30,
        min_disk_space_mb=10,
    )


@pytest.fixture
def storage(evidence_config):
    s = EvidenceStorage(evidence_config)
    s.initialize()
    return s


@pytest.fixture
def repo():
    return InMemoryEvidenceRepository()


class _StubDetector:
    """Reports a fixed face box regardless of frame content — used to
    test the anonymization pixel transformation without depending on the
    Haar cascade detecting hand-drawn synthetic art."""

    def __init__(self, boxes):
        self._boxes = boxes

    def detect(self, frame):
        return self._boxes


@pytest.fixture
def sample_frame():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[50:150, 50:150] = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    return frame


class TestPrivacyConfig:
    def test_default_mode_is_off(self):
        assert PrivacyConfig().mode == PrivacyMode.OFF

    def test_mode_configurable_via_constructor(self):
        assert PrivacyConfig(mode=PrivacyMode.FACE_BLUR).mode == PrivacyMode.FACE_BLUR
        assert PrivacyConfig(mode=PrivacyMode.FACE_PIXELATE).mode == PrivacyMode.FACE_PIXELATE


class TestFaceDetectorNeverRaisesOnNoFace:
    def test_blank_frame_returns_empty_list(self):
        detector = FaceDetector()
        frame = np.full((480, 640, 3), 220, dtype=np.uint8)
        assert detector.detect(frame) == []

    def test_none_frame_returns_empty_list(self):
        assert FaceDetector().detect(None) == []

    def test_empty_array_returns_empty_list(self):
        assert FaceDetector().detect(np.array([])) == []

    def test_no_identity_methods_exposed(self):
        """FaceDetector's public surface must never grow recognition/identity methods."""
        detector = FaceDetector()
        forbidden = ("recognize", "identify", "embed", "encode", "match")
        for method in dir(detector):
            if method.startswith("_"):
                continue
            for term in forbidden:
                assert term not in method.lower()


class TestFaceAnonymizerTransformation:
    def test_off_mode_leaves_frame_byte_identical(self, sample_frame):
        anonymizer = FaceAnonymizer(PrivacyConfig(mode=PrivacyMode.OFF))
        original = sample_frame.copy()
        result, count = anonymizer.process(sample_frame)
        assert count == 0
        assert np.array_equal(result, original)

    def test_no_faces_detected_leaves_frame_untouched(self, sample_frame):
        anonymizer = FaceAnonymizer(PrivacyConfig(mode=PrivacyMode.FACE_BLUR), detector=_StubDetector([]))
        original = sample_frame.copy()
        result, count = anonymizer.process(sample_frame)
        assert count == 0
        assert np.array_equal(result, original)

    def test_blur_mode_changes_region_pixels(self, sample_frame):
        original = sample_frame.copy()
        anonymizer = FaceAnonymizer(
            PrivacyConfig(mode=PrivacyMode.FACE_BLUR, expand_box_ratio=0.0),
            detector=_StubDetector([(50, 50, 100, 100)]),
        )
        result, count = anonymizer.process(sample_frame)
        assert count == 1
        assert not np.array_equal(result[50:150, 50:150], original[50:150, 50:150])
        assert np.array_equal(result[:50, :], original[:50, :])

    def test_pixelate_mode_changes_region_pixels(self, sample_frame):
        original = sample_frame.copy()
        anonymizer = FaceAnonymizer(
            PrivacyConfig(mode=PrivacyMode.FACE_PIXELATE, expand_box_ratio=0.0, pixelate_block_size=10),
            detector=_StubDetector([(50, 50, 100, 100)]),
        )
        result, count = anonymizer.process(sample_frame)
        assert count == 1
        assert not np.array_equal(result[50:150, 50:150], original[50:150, 50:150])

    def test_return_type_carries_no_identity_payload(self, sample_frame):
        anonymizer = FaceAnonymizer(PrivacyConfig(mode=PrivacyMode.FACE_BLUR), detector=_StubDetector([]))
        result = anonymizer.process(sample_frame)
        assert isinstance(result, tuple) and len(result) == 2
        frame_out, count = result
        assert isinstance(frame_out, np.ndarray)
        assert isinstance(count, int)


class TestEvidenceServicePrivacyIntegration:
    """
    Confirms anonymization happens BEFORE the frame reaches storage —
    the persisted JPEG bytes must already differ from what an
    OFF-mode capture of the same frame would have produced.
    """

    @pytest.mark.asyncio
    async def test_off_mode_stores_frame_unmodified(self, evidence_config, storage, repo, sample_frame):
        privacy_config = PrivacyConfig(mode=PrivacyMode.OFF)
        service = EvidenceService(evidence_config, storage, repo, privacy_config=privacy_config)

        record = await service.capture_snapshot(frame=sample_frame.copy(), incident_id=uuid4())

        assert record.privacy_mode_applied == "off"
        assert record.faces_anonymized == 0

    @pytest.mark.asyncio
    async def test_blur_mode_anonymizes_before_storage(self, evidence_config, storage, repo, sample_frame):
        privacy_config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR, expand_box_ratio=0.0)
        anonymizer = FaceAnonymizer(privacy_config, detector=_StubDetector([(50, 50, 100, 100)]))
        service = EvidenceService(
            evidence_config, storage, repo, privacy_config=privacy_config, anonymizer=anonymizer
        )

        record = await service.capture_snapshot(frame=sample_frame.copy(), incident_id=uuid4())

        assert record.privacy_mode_applied == "face_blur"
        assert record.faces_anonymized == 1

    @pytest.mark.asyncio
    async def test_stored_bytes_differ_between_off_and_blur_mode(
        self, evidence_config, repo, sample_frame, tmp_path
    ):
        """
        The strongest possible proof of "no unblurred copy stored": capture
        the SAME source frame once with privacy off and once with privacy
        on, and confirm the bytes actually written to disk differ.
        """
        storage_off = EvidenceStorage(EvidenceConfig(storage_path=str(tmp_path / "off"), min_disk_space_mb=10))
        storage_off.initialize()
        storage_blur = EvidenceStorage(EvidenceConfig(storage_path=str(tmp_path / "blur"), min_disk_space_mb=10))
        storage_blur.initialize()

        off_config = PrivacyConfig(mode=PrivacyMode.OFF)
        off_service = EvidenceService(evidence_config, storage_off, InMemoryEvidenceRepository(), privacy_config=off_config)

        blur_config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR, expand_box_ratio=0.0)
        blur_anonymizer = FaceAnonymizer(blur_config, detector=_StubDetector([(50, 50, 100, 100)]))
        blur_service = EvidenceService(
            evidence_config, storage_blur, InMemoryEvidenceRepository(),
            privacy_config=blur_config, anonymizer=blur_anonymizer,
        )

        off_record = await off_service.capture_snapshot(frame=sample_frame.copy(), incident_id=uuid4())
        blur_record = await blur_service.capture_snapshot(frame=sample_frame.copy(), incident_id=uuid4())

        off_bytes = await off_service.read_evidence_file(off_record.id)
        blur_bytes = await blur_service.read_evidence_file(blur_record.id)

        assert off_bytes != blur_bytes

    @pytest.mark.asyncio
    async def test_retention_override_by_privacy_mode(self, storage, repo, sample_frame, tmp_path):
        config = EvidenceConfig(
            storage_path=str(tmp_path / "store"),
            retention_days=90,
            retention_days_by_privacy_mode={"face_blur": 365},
            min_disk_space_mb=10,
        )
        privacy_config = PrivacyConfig(mode=PrivacyMode.FACE_BLUR, expand_box_ratio=0.0)
        anonymizer = FaceAnonymizer(privacy_config, detector=_StubDetector([]))
        service = EvidenceService(config, storage, repo, privacy_config=privacy_config, anonymizer=anonymizer)

        record = await service.capture_snapshot(frame=sample_frame.copy(), incident_id=uuid4())

        expected_days = (record.expires_at - record.captured_at).days
        assert expected_days in (364, 365)  # allow for microsecond rounding

    @pytest.mark.asyncio
    async def test_default_retention_used_when_no_override(self, storage, repo, sample_frame, tmp_path):
        config = EvidenceConfig(storage_path=str(tmp_path / "store2"), retention_days=30, min_disk_space_mb=10)
        privacy_config = PrivacyConfig(mode=PrivacyMode.OFF)
        service = EvidenceService(config, storage, repo, privacy_config=privacy_config)

        record = await service.capture_snapshot(frame=sample_frame.copy(), incident_id=uuid4())
        expected_days = (record.expires_at - record.captured_at).days
        assert expected_days in (29, 30)


class TestEvidenceAuditLog:
    @pytest.mark.asyncio
    async def test_cleanup_expired_writes_audit_entry(self, evidence_config, storage, repo, sample_frame):
        from datetime import datetime, timezone

        from app.evidence import EvidenceAuditAction, EvidenceAuditLog

        audit = EvidenceAuditLog()
        service = EvidenceService(evidence_config, storage, repo, audit_log=audit)

        record = await service.capture_snapshot(frame=sample_frame.copy(), incident_id=uuid4())
        record.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        await repo.create(record)

        cleaned = await service.cleanup_expired()
        assert cleaned >= 1

        entries = audit.get_entries(action=EvidenceAuditAction.EXPIRED_CLEANUP)
        assert len(entries) >= 1
        assert entries[0].evidence_id == record.id

    def test_audit_log_entries_are_append_only_query_filters(self):
        from app.evidence import EvidenceAuditAction, EvidenceAuditLog

        audit = EvidenceAuditLog()
        eid = uuid4()
        audit.log(action=EvidenceAuditAction.LIST_VIEWED, evidence_id=eid, user_id="u1")
        audit.log(action=EvidenceAuditAction.FILE_DOWNLOADED, evidence_id=eid, user_id="u2")

        assert audit.total_entries == 2
        by_user = audit.get_entries(user_id="u1")
        assert len(by_user) == 1
        assert by_user[0].user_id == "u1"
