"""
Document Store

Thin async CRUD helper over the generic `documents` table. Repositories use
this to persist/load Pydantic entities as JSON, without embedding SQL in the
domain layer. Each instance is scoped to a single entity_type.

All methods open their own short-lived session from the shared session
factory, so callers don't have to manage sessions — appropriate for the
in-process, low-concurrency workload of this academic prototype.
"""

import json
from typing import List, Optional

from sqlalchemy import delete, func, select

from .models_orm import Document
from .session import get_session_factory


class DocumentStore:
    """Async CRUD over the documents table for one entity_type."""

    def __init__(self, entity_type: str):
        self.entity_type = entity_type

    async def upsert(self, entity_id: str, payload: dict, seq: Optional[int] = None) -> int:
        """
        Insert or update a document. Returns the (possibly newly assigned)
        seq value for this row. If seq is None on a new row, the next
        sequence number for this entity_type is assigned atomically.
        """
        factory = get_session_factory()
        async with factory() as session:
            async with session.begin():
                existing = (
                    await session.execute(
                        select(Document).where(
                            Document.entity_type == self.entity_type,
                            Document.entity_id == entity_id,
                        )
                    )
                ).scalar_one_or_none()

                if existing is None:
                    if seq is None:
                        max_seq = (
                            await session.execute(
                                select(func.coalesce(func.max(Document.seq), 0)).where(
                                    Document.entity_type == self.entity_type
                                )
                            )
                        ).scalar_one()
                        seq = int(max_seq) + 1
                    row = Document(
                        entity_type=self.entity_type,
                        entity_id=entity_id,
                        seq=seq,
                        payload=json.dumps(payload, default=str),
                    )
                    session.add(row)
                    return seq
                else:
                    existing.payload = json.dumps(payload, default=str)
                    if seq is not None:
                        existing.seq = seq
                    return existing.seq

    async def get(self, entity_id: str) -> Optional[dict]:
        factory = get_session_factory()
        async with factory() as session:
            row = (
                await session.execute(
                    select(Document).where(
                        Document.entity_type == self.entity_type,
                        Document.entity_id == entity_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            data = json.loads(row.payload)
            data["_seq"] = row.seq
            return data

    async def list_all(self) -> List[dict]:
        """Return all documents of this entity_type, newest row first."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (
                await session.execute(
                    select(Document)
                    .where(Document.entity_type == self.entity_type)
                    .order_by(Document.created_at.desc(), Document.id.desc())
                )
            ).scalars().all()
            result = []
            for row in rows:
                data = json.loads(row.payload)
                data["_seq"] = row.seq
                result.append(data)
            return result

    async def delete(self, entity_id: str) -> None:
        factory = get_session_factory()
        async with factory() as session:
            async with session.begin():
                await session.execute(
                    delete(Document).where(
                        Document.entity_type == self.entity_type,
                        Document.entity_id == entity_id,
                    )
                )

    async def count(self) -> int:
        factory = get_session_factory()
        async with factory() as session:
            return (
                await session.execute(
                    select(func.count(Document.id)).where(
                        Document.entity_type == self.entity_type
                    )
                )
            ).scalar_one()

    async def clear(self) -> None:
        """Delete all rows for this entity_type (testing/reset only)."""
        factory = get_session_factory()
        async with factory() as session:
            async with session.begin():
                await session.execute(
                    delete(Document).where(Document.entity_type == self.entity_type)
                )
