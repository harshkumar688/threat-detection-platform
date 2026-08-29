"""
Unit tests for the evidence capture subsystem.

Tests:
- Snapshot capture and storage
- File path safety (no traversal)
- Retention policy and expiration
- Ring buffer behavior
- Repository operations
- Service orchestration
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from pathlib import Path

from app.evidence import (
    EvidenceConfig,
    EvidenceRecord,
    EvidenceType,
    EvidenceService,
    EvidenceStorage,
    FrameRingBuffer,
    InMemoryEvidenceRepository,
)
from app.evidence.storage import EvidenceStorage


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def config(tmp_path):
    return EvidenceConfig(
        storage_path=str(tmp_path / "evidence_store"),
        snapshot_quality=85,
        retention_days=30,
        buffer_max_frames=50,
        min_disk_space_mb=10,
    )


@pytest.fixture
def storage(config):
    s = EvidenceStorage(config)
    s.initialize()
    return s


@pytest.fixture
def repo():
    return InMemoryEvidenceRepository()


@pytest.fixture
def service(config, storage, repo):
    return EvidenceService(config, storage, repo)


@pytest.fixture
def sample_frame():
    """640x480 BGR frame with some content."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:200, 200:400] = (0, 0, 255)  # Red rectangle
    return frame


@pytest.fixture
def incident_id():
    return uuid4()


# =============================================================================
# Path Safety Tests
# =============================================================================

class TestPathSafety:
    """Tests that file path security is enforced."""

    def test_safe_path_valid(self):
        assert EvidenceStorage._is_safe_path("2026/08/18/abc123.jpg") is True
        assert EvidenceStorage._is_safe_path("2026/01/01/a-b-c_d.mp4") is True

    def test_path_traversal_blocked(self):
        assert EvidenceStorage._is_safe_path("../../../etc/passwd") is False
        assert EvidenceStorage._is_safe_path("2026/../../secret.txt") is False
        assert EvidenceStorage._is_safe_path("..") is False

    def test_absolute_path_blocked(self):
        assert EvidenceStorage._is_safe_path("/etc/passwd") is False
        assert EvidenceStorage._is_safe_path("\\windows\\system32") is False

    def test_null_byte_blocked(self):
        assert EvidenceStorage._is_safe_path("file\x00.jpg") is False

    def test_colon_blocked(self):
        assert EvidenceStorage._is_safe_path("C:\\file.jpg") is False
        assert EvidenceStorage._is_safe_path("C:/file.jpg") is False

    def test_empty_path_blocked(self):
        assert EvidenceStorage._is_safe_path("") is False

    def test_dot_component_blocked(self):
        assert EvidenceStorage._is_safe_path("./file.jpg") is False

    def test_special_chars_blocked(self):
        assert EvidenceStorage._is_safe_path("file name.jpg") is False  # Space
        assert EvidenceStorage._is_safe_path("file@name.jpg") is False  # @

    def test_sanitize_extension(self):
        assert EvidenceStorage._sanitize_extension(".jpg") == ".jpg"
        assert EvidenceStorage._sanitize_extension(".mp4") == ".mp4"
        assert EvidenceStorage._sanitize_extension(".exe") == ".bin"
        assert EvidenceStorage._sanitize_extension("jpg") == ".jpg"
        assert EvidenceStorage._sanitize_extension(".PHP") == ".bin"


# =============================================================================
# Storage Tests
# =============================================================================

class TestEvidenceStorage:
    """Tests for physical file storage."""

    def test_initialize_creates_directory(self, config, tmp_path):
        s = EvidenceStorage(config)
        s.initialize()
        assert Path(config.storage_path).exists()

    def test_save_snapshot(self, storage, sample_frame):
        evidence_id = uuid4()
        relative_path, file_size = storage.save_snapshot(sample_frame, evidence_id)

        assert relative_path.endswith(".jpg")
        assert str(evidence_id) in relative_path
        assert file_size > 0

        # Verify file exists on disk
        abs_path = Path(storage.config.storage_path) / relative_path
        assert abs_path.exists()

    def test_save_and_read(self, storage, sample_frame):
        evidence_id = uuid4()
        relative_path, _ = storage.save_snapshot(sample_frame, evidence_id)

        # Read back
        data = storage.read_file(relative_path)
        assert data is not None
        assert len(data) > 0

    def test_read_nonexistent(self, storage):
        data = storage.read_file("2026/01/01/nonexistent.jpg")
        assert data is None

    def test_read_unsafe_path_returns_none(self, storage):
        data = storage.read_file("../../etc/passwd")
        assert data is None

    def test_delete_file(self, storage, sample_frame):
        evidence_id = uuid4()
        relative_path, _ = storage.save_snapshot(sample_frame, evidence_id)

        assert storage.delete_file(relative_path) is True
        assert storage.read_file(relative_path) is None

    def test_delete_nonexistent(self, storage):
        assert storage.delete_file("2026/01/01/nope.jpg") is False

    def test_delete_unsafe_path_fails(self, storage):
        assert storage.delete_file("../secret.txt") is False

    def test_save_raw_bytes(self, storage):
        evidence_id = uuid4()
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Fake JPEG header
        relative_path, file_size = storage.save_raw_bytes(data, evidence_id, ".jpg")

        assert file_size == len(data)
        assert str(evidence_id) in relative_path
        assert relative_path.endswith(".jpg")

    def test_disk_usage_info(self, storage):
        info = storage.get_disk_usage()
        assert "free_mb" in info or "error" in info


# =============================================================================
# Ring Buffer Tests
# =============================================================================

class TestFrameRingBuffer:
    """Tests for the pre-event frame ring buffer."""

    def test_push_and_size(self):
        buf = FrameRingBuffer(max_frames=10)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        buf.push(frame, frame_number=1)
        assert buf.size == 1

        for i in range(5):
            buf.push(frame, frame_number=i + 2)
        assert buf.size == 6

    def test_max_capacity(self):
        buf = FrameRingBuffer(max_frames=5)
        frame = np.zeros((50, 50, 3), dtype=np.uint8)

        for i in range(20):
            buf.push(frame, frame_number=i)

        assert buf.size == 5  # Oldest discarded
        assert buf.is_full

    def test_get_last_n(self):
        buf = FrameRingBuffer(max_frames=100)
        frame = np.zeros((50, 50, 3), dtype=np.uint8)

        for i in range(10):
            buf.push(frame, frame_number=i + 1)

        last_3 = buf.get_last_n(3)
        assert len(last_3) == 3
        assert last_3[0].frame_number == 8  # Oldest of last 3
        assert last_3[2].frame_number == 10  # Newest

    def test_get_last_n_more_than_available(self):
        buf = FrameRingBuffer(max_frames=100)
        frame = np.zeros((50, 50, 3), dtype=np.uint8)

        buf.push(frame, frame_number=1)
        buf.push(frame, frame_number=2)

        result = buf.get_last_n(100)
        assert len(result) == 2

    def test_get_last_seconds(self):
        buf = FrameRingBuffer(max_frames=100)
        frame = np.zeros((50, 50, 3), dtype=np.uint8)

        for i in range(60):
            buf.push(frame, frame_number=i)

        # At 30fps, 2 seconds = 60 frames
        result = buf.get_last_seconds(2.0, fps=30.0)
        assert len(result) == 60

    def test_empty_buffer(self):
        buf = FrameRingBuffer(max_frames=10)
        assert buf.is_empty
        assert buf.size == 0
        assert buf.get_last_n(5) == []
        assert buf.oldest_frame is None
        assert buf.newest_frame is None

    def test_oldest_newest(self):
        buf = FrameRingBuffer(max_frames=10)
        frame = np.zeros((50, 50, 3), dtype=np.uint8)

        buf.push(frame, frame_number=1)
        buf.push(frame, frame_number=2)
        buf.push(frame, frame_number=3)

        assert buf.oldest_frame.frame_number == 1
        assert buf.newest_frame.frame_number == 3

    def test_clear(self):
        buf = FrameRingBuffer(max_frames=10)
        frame = np.zeros((50, 50, 3), dtype=np.uint8)

        buf.push(frame, frame_number=1)
        buf.push(frame, frame_number=2)
        buf.clear()

        assert buf.is_empty
        assert buf.size == 0

    def test_invalid_max_frames(self):
        with pytest.raises(ValueError):
            FrameRingBuffer(max_frames=0)

    def test_duration_seconds(self):
        buf = FrameRingBuffer(max_frames=100)
        frame = np.zeros((50, 50, 3), dtype=np.uint8)

        t1 = datetime(2026, 8, 18, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 8, 18, 10, 0, 5, tzinfo=timezone.utc)

        buf.push(frame, frame_number=1, timestamp=t1)
        buf.push(frame, frame_number=2, timestamp=t2)

        assert buf.duration_seconds == 5.0


# =============================================================================
# Repository Tests
# =============================================================================

class TestInMemoryRepository:
    """Tests for the in-memory evidence repository."""

    @pytest.mark.asyncio
    async def test_create_and_get(self, repo, incident_id):
        record = EvidenceRecord(
            incident_id=incident_id,
            evidence_type=EvidenceType.SNAPSHOT,
            file_path="2026/08/18/test.jpg",
            file_name="test.jpg",
            file_size_bytes=1000,
        )
        created = await repo.create(record)
        assert created.id == record.id

        retrieved = await repo.get_by_id(record.id)
        assert retrieved is not None
        assert retrieved.incident_id == incident_id

    @pytest.mark.asyncio
    async def test_list_by_incident(self, repo, incident_id):
        for i in range(3):
            record = EvidenceRecord(
                incident_id=incident_id,
                evidence_type=EvidenceType.SNAPSHOT,
                file_path=f"2026/08/18/img{i}.jpg",
                file_name=f"img{i}.jpg",
                file_size_bytes=500,
            )
            await repo.create(record)

        results = await repo.list_by_incident(incident_id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_list_excludes_deleted(self, repo, incident_id):
        record = EvidenceRecord(
            incident_id=incident_id,
            evidence_type=EvidenceType.SNAPSHOT,
            file_path="2026/08/18/deleted.jpg",
            file_name="deleted.jpg",
            file_size_bytes=100,
        )
        await repo.create(record)
        await repo.mark_deleted(record.id)

        results = await repo.list_by_incident(incident_id)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_expired(self, repo, incident_id):
        # Expired record
        expired = EvidenceRecord(
            incident_id=incident_id,
            evidence_type=EvidenceType.SNAPSHOT,
            file_path="old.jpg",
            file_name="old.jpg",
            file_size_bytes=100,
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        await repo.create(expired)

        # Valid record
        valid = EvidenceRecord(
            incident_id=incident_id,
            evidence_type=EvidenceType.SNAPSHOT,
            file_path="new.jpg",
            file_name="new.jpg",
            file_size_bytes=100,
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        await repo.create(valid)

        expired_list = await repo.get_expired()
        assert len(expired_list) == 1
        assert expired_list[0].id == expired.id


# =============================================================================
# Service Integration Tests
# =============================================================================

class TestEvidenceService:
    """Tests for the evidence service (orchestration layer)."""

    @pytest.mark.asyncio
    async def test_capture_snapshot(self, service, sample_frame, incident_id):
        record = await service.capture_snapshot(
            frame=sample_frame,
            incident_id=incident_id,
            camera_id="cam-01",
            frame_number=42,
            annotations=[{"class": "handgun", "bbox": [0.3, 0.3, 0.6, 0.7]}],
        )

        assert record.id is not None
        assert record.incident_id == incident_id
        assert record.evidence_type == EvidenceType.SNAPSHOT
        assert record.file_size_bytes > 0
        assert record.camera_id == "cam-01"
        assert record.frame_number == 42
        assert record.mime_type == "image/jpeg"
        assert record.expires_at is not None

    @pytest.mark.asyncio
    async def test_capture_sets_retention(self, service, sample_frame, incident_id, config):
        record = await service.capture_snapshot(
            frame=sample_frame,
            incident_id=incident_id,
        )

        expected_expiry = record.captured_at + timedelta(days=config.retention_days)
        diff = abs((record.expires_at - expected_expiry).total_seconds())
        assert diff < 1  # Within 1 second

    @pytest.mark.asyncio
    async def test_retrieve_evidence_file(self, service, sample_frame, incident_id):
        record = await service.capture_snapshot(
            frame=sample_frame,
            incident_id=incident_id,
        )

        # Read file back
        data = await service.read_evidence_file(record.id)
        assert data is not None
        assert len(data) > 0
        # Should be valid JPEG (starts with FF D8)
        assert data[:2] == b"\xff\xd8"

    @pytest.mark.asyncio
    async def test_get_evidence_for_incident(self, service, sample_frame, incident_id):
        await service.capture_snapshot(frame=sample_frame, incident_id=incident_id)
        await service.capture_snapshot(frame=sample_frame, incident_id=incident_id)

        records = await service.get_evidence_for_incident(incident_id)
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, service, sample_frame, incident_id, repo):
        record = await service.capture_snapshot(
            frame=sample_frame,
            incident_id=incident_id,
        )
        # Manually expire it
        record.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        await repo.create(record)  # Update in-memory

        cleaned = await service.cleanup_expired()
        assert cleaned >= 1

    @pytest.mark.asyncio
    async def test_storage_info(self, service):
        info = service.get_storage_info()
        assert "storage_path" in info
        assert "retention_days" in info
        assert "disk_usage" in info


# =============================================================================
# Evidence Model Tests
# =============================================================================

class TestEvidenceRecord:
    """Tests for the EvidenceRecord model."""

    def test_set_retention(self):
        record = EvidenceRecord(
            incident_id=uuid4(),
            evidence_type=EvidenceType.SNAPSHOT,
            file_path="test.jpg",
            file_name="test.jpg",
            file_size_bytes=100,
            captured_at=datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc),
        )
        record.set_retention(90)
        assert record.expires_at == datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)

    def test_is_expired_true(self):
        record = EvidenceRecord(
            incident_id=uuid4(),
            evidence_type=EvidenceType.SNAPSHOT,
            file_path="test.jpg",
            file_name="test.jpg",
            file_size_bytes=100,
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        assert record.is_expired is True

    def test_is_expired_false(self):
        record = EvidenceRecord(
            incident_id=uuid4(),
            evidence_type=EvidenceType.SNAPSHOT,
            file_path="test.jpg",
            file_name="test.jpg",
            file_size_bytes=100,
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        assert record.is_expired is False

    def test_is_expired_no_expiry(self):
        record = EvidenceRecord(
            incident_id=uuid4(),
            evidence_type=EvidenceType.SNAPSHOT,
            file_path="test.jpg",
            file_name="test.jpg",
            file_size_bytes=100,
            expires_at=None,
        )
        assert record.is_expired is False

    def test_to_dict(self):
        record = EvidenceRecord(
            incident_id=uuid4(),
            evidence_type=EvidenceType.CLIP,
            file_path="2026/08/18/clip.mp4",
            file_name="clip.mp4",
            file_size_bytes=5000000,
            mime_type="video/mp4",
            duration_seconds=20.0,
            camera_id="cam-lobby",
        )
        d = record.to_dict()
        assert d["evidence_type"] == "clip"
        assert d["mime_type"] == "video/mp4"
        assert d["duration_seconds"] == 20.0
        assert d["camera_id"] == "cam-lobby"
