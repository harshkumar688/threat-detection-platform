"""
ORM Storage Model

A single generic `documents` table stores every persisted entity as a JSON
payload. This deliberately avoids hand-writing an ORM class per domain model
(the domain models are Pydantic) while still giving real, queryable, durable
persistence.

Columns:
    entity_type : which kind of entity (e.g. "incident", "user", "camera")
    entity_id   : the entity's UUID/string id
    seq         : a monotonic per-entity-type sequence (for human-readable
                  numbers like incident_number, assigned at insert time)
    payload     : the full entity serialized as JSON
    created_at  : row creation timestamp (indexed for ordering)

The (entity_type, entity_id) pair is unique — that's the primary lookup key.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_entity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
