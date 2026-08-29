"""
Evidence Schemas
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceResponse(BaseModel):
    """Evidence metadata response."""

    id: str
    incident_id: str
    evidence_type: str  # snapshot, clip
    file_name: str
    file_size_bytes: int
    mime_type: str
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    camera_id: str = ""
    captured_at: str
    expires_at: str | None = None
    is_expired: bool = False
    privacy_mode_applied: str = "off"
    faces_anonymized: int = 0

    model_config = {"from_attributes": True}


class EvidenceListResponse(BaseModel):
    """Evidence list for an incident."""

    incident_id: str
    items: List[EvidenceResponse]
    total: int
