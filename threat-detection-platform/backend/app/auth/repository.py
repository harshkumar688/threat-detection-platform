"""
User Repository

Data access layer for user management.
Abstract interface + in-memory implementation.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from .models import User, UserRole


class UserRepository(ABC):
    """Abstract user repository."""

    @abstractmethod
    async def create(self, user: User) -> User:
        ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    @abstractmethod
    async def update(self, user: User) -> User:
        ...

    @abstractmethod
    async def list_all(self, is_active: Optional[bool] = None) -> List[User]:
        ...

    @abstractmethod
    async def count(self) -> int:
        ...


class InMemoryUserRepository(UserRepository):
    """In-memory implementation for testing."""

    def __init__(self):
        self._users: Dict[UUID, User] = {}
        self._email_index: Dict[str, UUID] = {}

    async def create(self, user: User) -> User:
        self._users[user.id] = user
        self._email_index[user.email.lower()] = user.id
        return user

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        uid = self._email_index.get(email.lower())
        if uid is None:
            return None
        return self._users.get(uid)

    async def update(self, user: User) -> User:
        user.updated_at = datetime.now(timezone.utc)
        self._users[user.id] = user
        return user

    async def list_all(self, is_active: Optional[bool] = None) -> List[User]:
        users = list(self._users.values())
        if is_active is not None:
            users = [u for u in users if u.is_active == is_active]
        return sorted(users, key=lambda u: u.created_at, reverse=True)

    async def count(self) -> int:
        return len(self._users)

    def clear(self):
        self._users.clear()
        self._email_index.clear()


class SqlUserRepository(UserRepository):
    """
    Durable user repository backed by the generic document store.

    The User model stores a password_hash field. This never appears in API
    responses (the service layer strips it), and persisting it is necessary
    (otherwise users can't log in after a restart). The hash is bcrypt, never
    plaintext — safe to store.
    """

    def __init__(self):
        from app.db import DocumentStore
        self._store = DocumentStore("user")

    async def create(self, user: User) -> User:
        await self._store.upsert(str(user.id), user.model_dump(mode="json"))
        return user

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        data = await self._store.get(str(user_id))
        return User(**{k: v for k, v in data.items() if k != "_seq"}) if data else None

    async def get_by_email(self, email: str) -> Optional[User]:
        for data in await self._store.list_all():
            user = User(**{k: v for k, v in data.items() if k != "_seq"})
            if user.email.lower() == email.lower():
                return user
        return None

    async def update(self, user: User) -> User:
        user.updated_at = datetime.now(timezone.utc)
        await self._store.upsert(str(user.id), user.model_dump(mode="json"))
        return user

    async def list_all(self, is_active: Optional[bool] = None) -> List[User]:
        results = [
            User(**{k: v for k, v in d.items() if k != "_seq"})
            for d in await self._store.list_all()
        ]
        if is_active is not None:
            results = [u for u in results if u.is_active == is_active]
        return sorted(results, key=lambda u: u.created_at, reverse=True)

    async def count(self) -> int:
        return await self._store.count()

    async def clear(self):
        await self._store.clear()
