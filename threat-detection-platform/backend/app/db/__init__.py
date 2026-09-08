"""
Database Layer

Real, durable persistence for the platform.

- session.py        : async SQLAlchemy engine + session factory + init_db()
- models_orm.py     : the single generic `documents` storage table
- document_store.py : async CRUD helper repositories build on

Default backend is a local SQLite file (zero setup, survives restarts). The
exact same code runs on PostgreSQL by setting DATABASE_URL — no code change.
"""

from .document_store import DocumentStore
from .session import get_database_url, get_engine, get_session, get_session_factory, init_db

__all__ = [
    "DocumentStore",
    "get_database_url",
    "get_engine",
    "get_session",
    "get_session_factory",
    "init_db",
]
