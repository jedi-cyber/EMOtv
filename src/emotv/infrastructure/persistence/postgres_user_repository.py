from __future__ import annotations

from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.role import Role
from emotv.domain.user import User
from emotv.infrastructure.persistence.models import UserRecord


class PostgresUserRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def save(self, user: User) -> User:
        if not isinstance(user, User):
            raise TypeError("user debe ser User")
        with self._factory.begin() as db:
            row = db.get(UserRecord, user.id)
            if row is None:
                db.add(UserRecord(id=user.id, email=user.email,
                    password_hash=user.password_hash, role=user.role.value,
                    is_active=user.is_active, created_at=user.created_at))
            else:
                row.email, row.password_hash = user.email, user.password_hash
                row.role, row.is_active = user.role.value, user.is_active
                row.created_at = user.created_at
        return user

    def get_by_id(self, user_id: str) -> User | None:
        with self._factory() as db:
            row = db.get(UserRecord, _text(user_id, "user_id"))
            return None if row is None else self._domain(row)

    def get_by_email(self, email: str) -> User | None:
        value = _text(email, "email").lower()
        with self._factory() as db:
            row = db.scalar(select(UserRecord).where(UserRecord.email == value))
            return None if row is None else self._domain(row)

    def list_all(self) -> tuple[User, ...]:
        with self._factory() as db:
            rows = db.scalars(select(UserRecord).order_by(UserRecord.created_at, UserRecord.id)).all()
            return tuple(self._domain(row) for row in rows)

    @staticmethod
    def _domain(row: UserRecord) -> User:
        created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
        return User(row.id, row.email, row.password_hash, Role(row.role), created, row.is_active)


def _text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} debe ser str")
    result = value.strip()
    if not result:
        raise ValueError(f"{name} no puede estar vacío")
    return result
