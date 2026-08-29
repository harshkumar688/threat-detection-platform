"""
Evidence Router

Endpoints:
- GET /evidence/{incident_id}         → List evidence for an incident
- GET /evidence/file/{evidence_id}    → Download evidence file (restricted)
- GET /evidence/audit/log             → View evidence access audit trail (admin)
- GET /evidence/privacy/status        → View current privacy configuration

Wired to the real EvidenceService (app/evidence). Metadata comes from the
EvidenceRepository; media bytes are read from EvidenceStorage. No evidence
is ever served without authentication, file paths are never derived from
user input, and every list/download/denied-access is recorded in the
evidence access audit log (separate from the auth audit log).

Access restrictions:
- Viewing metadata (list) requires VIEW_EVIDENCE (all roles).
- Downloading the actual file requires DOWNLOAD_EVIDENCE — admin and
  operator only. Viewers can see that evidence exists but not fetch it.
- Viewing the audit trail requires VIEW_EVIDENCE_AUDIT_LOG — admin only.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.api.deps import CurrentUser, get_current_user, require_permission
from app.auth.models import Permission
from app.core.exceptions import ForbiddenError, NotFoundError
from app.evidence import (
    EvidenceAuditAction,
    EvidenceAuditLog,
    EvidenceConfig,
    EvidenceService,
    EvidenceStorage,
    InMemoryEvidenceRepository,
)
from app.privacy import PrivacyConfig
from app.schemas.evidence import EvidenceListResponse, EvidenceResponse

router = APIRouter(prefix="/evidence", tags=["Evidence"])

# Service instance (in production, injected via Depends with DB session + real storage path)
_config = EvidenceConfig()
_storage = EvidenceStorage(_config)
_storage.initialize()
_repo = InMemoryEvidenceRepository()
_privacy_config = PrivacyConfig()
_audit_log = EvidenceAuditLog()
_service = EvidenceService(
    _config, _storage, _repo, privacy_config=_privacy_config, audit_log=_audit_log
)


def _record_to_response(record) -> EvidenceResponse:
    """Convert an EvidenceRecord domain model to its API response schema."""
    return EvidenceResponse(
        id=str(record.id),
        incident_id=str(record.incident_id),
        evidence_type=record.evidence_type.value,
        file_name=record.file_name,
        file_size_bytes=record.file_size_bytes,
        mime_type=record.mime_type,
        width=record.width,
        height=record.height,
        duration_seconds=record.duration_seconds,
        camera_id=record.camera_id,
        captured_at=record.captured_at.isoformat(),
        expires_at=record.expires_at.isoformat() if record.expires_at else None,
        is_expired=record.is_expired,
        privacy_mode_applied=record.privacy_mode_applied,
        faces_anonymized=record.faces_anonymized,
    )


@router.get(
    "/{incident_id}",
    response_model=EvidenceListResponse,
    summary="List evidence for incident",
    description="Get all evidence items (snapshots, clips) associated with an incident.",
)
async def list_evidence(
    incident_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """
    List all evidence for an incident.

    Returns metadata only — use /evidence/file/{id} for actual download.
    Recorded in the evidence access audit log.
    """
    try:
        incident_uuid = UUID(incident_id)
    except ValueError:
        raise NotFoundError("Incident", incident_id)

    records = await _service.get_evidence_for_incident(incident_uuid)

    _audit_log.log(
        action=EvidenceAuditAction.LIST_VIEWED,
        incident_id=incident_uuid,
        user_id=user.user_id,
        user_role=user.role,
        ip_address=request.client.host if request.client else None,
        details=f"{len(records)} item(s) returned",
    )

    return EvidenceListResponse(
        incident_id=incident_id,
        items=[_record_to_response(r) for r in records],
        total=len(records),
    )


@router.get(
    "/file/{evidence_id}",
    summary="Download evidence file",
    description=(
        "Download the actual evidence media file (JPEG/MP4). "
        "Requires authentication. File is served directly — not publicly accessible."
    ),
    responses={
        200: {"description": "Evidence file bytes", "content": {"image/jpeg": {}, "video/mp4": {}}},
        404: {"description": "Evidence not found"},
    },
)
async def download_evidence(
    evidence_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Download an evidence file.

    The file is served with appropriate Content-Type header. Requires the
    DOWNLOAD_EVIDENCE permission (admin/operator) — viewers can see that
    evidence exists via the list endpoint but cannot fetch the media
    itself. Both successful downloads and denied attempts are recorded in
    the evidence access audit log.
    """
    from app.auth.models import UserRole
    from app.auth.permissions import has_permission

    try:
        evidence_uuid = UUID(evidence_id)
    except ValueError:
        raise NotFoundError("Evidence", evidence_id)

    ip_address = request.client.host if request.client else None

    try:
        role = UserRole(user.role)
    except ValueError:
        role = None

    if role is None or not has_permission(role, Permission.DOWNLOAD_EVIDENCE):
        _audit_log.log(
            action=EvidenceAuditAction.ACCESS_DENIED,
            evidence_id=evidence_uuid,
            user_id=user.user_id,
            user_role=user.role,
            ip_address=ip_address,
            details="Missing DOWNLOAD_EVIDENCE permission",
        )
        raise ForbiddenError("Downloading evidence requires operator or admin role")

    record = await _service.get_evidence(evidence_uuid)
    if record is None or record.is_deleted:
        raise NotFoundError("Evidence", evidence_id)

    data = await _service.read_evidence_file(evidence_uuid)
    if data is None:
        raise NotFoundError("Evidence", evidence_id)

    _audit_log.log(
        action=EvidenceAuditAction.FILE_DOWNLOADED,
        evidence_id=evidence_uuid,
        incident_id=record.incident_id,
        user_id=user.user_id,
        user_role=user.role,
        ip_address=ip_address,
    )

    return Response(content=data, media_type=record.mime_type)


@router.get(
    "/audit/log",
    summary="View evidence access audit trail",
    description=(
        "Full audit trail of evidence access events (list views, downloads, "
        "denied attempts, retention cleanups). Requires admin role."
    ),
)
async def get_evidence_audit_log(
    evidence_id: str | None = None,
    incident_id: str | None = None,
    limit: int = 100,
    user: CurrentUser = Depends(require_permission(Permission.VIEW_EVIDENCE_AUDIT_LOG)),
):
    """Admin-only view of the evidence access audit log."""
    evidence_uuid = None
    if evidence_id:
        try:
            evidence_uuid = UUID(evidence_id)
        except ValueError:
            pass

    incident_uuid = None
    if incident_id:
        try:
            incident_uuid = UUID(incident_id)
        except ValueError:
            pass

    entries = _audit_log.get_entries(
        evidence_id=evidence_uuid, incident_id=incident_uuid, limit=limit
    )

    return {
        "total": len(entries),
        "entries": [
            {
                "id": str(e.id),
                "action": e.action.value,
                "evidence_id": str(e.evidence_id) if e.evidence_id else None,
                "incident_id": str(e.incident_id) if e.incident_id else None,
                "user_id": e.user_id,
                "user_role": e.user_role,
                "ip_address": e.ip_address,
                "details": e.details,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in entries
        ],
    }


@router.get(
    "/privacy/status",
    summary="View current privacy configuration",
    description=(
        "Returns the privacy mode currently applied to newly captured "
        "evidence, plus its documented limitations. Configuration is "
        "environment-driven (PRIVACY_MODE) and cannot be changed via API — "
        "changing production privacy behavior requires a deployment "
        "config change, not a runtime toggle any user can flip."
    ),
)
async def get_privacy_status(user: CurrentUser = Depends(get_current_user)):
    """View the active privacy configuration and its known limitations."""
    return {
        "mode": _privacy_config.mode.value,
        "description": {
            "off": "No anonymization is applied to captured evidence.",
            "face_blur": "Detected face regions are Gaussian-blurred before evidence is stored.",
            "face_pixelate": "Detected face regions are pixelated before evidence is stored.",
        }[_privacy_config.mode.value],
        "limitations": [
            "Face detection uses a classical Haar-cascade localizer, not a deep model — "
            "it can miss non-frontal, poorly lit, occluded, or very small faces.",
            "This module performs face LOCALIZATION only. It never performs face "
            "recognition, identity matching, or biometric inference of any kind.",
            "Anonymization is applied once, destructively, at capture time. There is "
            "no unblurred copy retained anywhere — this also means a missed face "
            "cannot be blurred retroactively after the fact.",
            "Privacy mode is a deployment-level configuration value, not a per-request "
            "toggle, to prevent inconsistent anonymization across evidence from the "
            "same system.",
        ],
    }
