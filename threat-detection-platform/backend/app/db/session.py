"""
Database Session & Engine

Async SQLAlchemy engine + session factory.

Design note (why this shape):
The domain models in this project are Pydantic models, not SQLAlchemy ORM
classes, and the service/repository layers were built against abstract
repository interfaces. To add real persistence with the *smallest* safe
change, we use a generic document-style store: each entity is persisted as
a row of (id, entity_type, payload_json, + a few indexed columns) in a
single `documents` table. Repositories serialize/deserialize their Pydantic
models to/from that JSON payload.

This keeps every service and router untouched — we only change which
repository implementation is instantiated. It also stays swappable: the same
SQLAlchemy async code runs on SQLite (default, zero-setup, file-based) or
PostgreSQL by changing DATABASE_URL only.

    DATABASE_URL=sqlite+aiosqlite:///./threat_platform.db          (default)
    DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname   (production)
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models_orm import Base


def _default_sqlite_url() -> str:
    # Store the DB file at the backend root so it's stable regardless of cwd.
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db_path = os.path.join(backend_root, "threat_platform.db")
    # aiosqlite requires forward slashes in the URL even on Windows.
    return f"sqlite+aiosqlite:///{db_path.replace(os.sep, '/')}"


def get_database_url() -> str:
    """Resolve the database URL from env, defaulting to a local SQLite file."""
    return os.getenv("DATABASE_URL_RUNTIME") or os.getenv("DATABASE_URL") or _default_sqlite_url()


_engine = None
_session_factory: async_sessionmaker | None = None


def get_engine():
    """Lazily create and cache the async engine."""
    global _engine
    if _engine is None:
        url = get_database_url()
        # check_same_thread only applies to SQLite; harmless to pass via connect_args.
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_async_engine(url, echo=False, connect_args=connect_args, future=True)
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Lazily create and cache the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def init_db() -> None:
    """Create tables if they don't exist. Called once at application startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield a database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
