from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from emotv.application.mobile_auth_service import MobileSession
from emotv.infrastructure.persistence.models import MobileSessionRecord

_FIELDS = ("id", "user_id", "refresh_token_hash", "token_version", "created_at", "expires_at", "last_used_at",
           "previous_token_hash", "revoked_at")


class PostgresMobileSessionRepository:
    """Sesiones del aplicativo móvil; los tokens de renovación, solo como SHA-256."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def add(self, session: MobileSession) -> MobileSession:
        with self._factory.begin() as db:
            db.add(MobileSessionRecord(**{name: getattr(session, name) for name in _FIELDS}))
        return session

    def save(self, session: MobileSession) -> MobileSession:
        with self._factory.begin() as db:
            record = db.get(MobileSessionRecord, session.id)
            for name in _FIELDS[1:]:
                setattr(record, name, getattr(session, name))
        return session

    def get(self, session_id: str) -> MobileSession | None:
        with self._factory() as db:
            return self._to_domain(db.get(MobileSessionRecord, session_id))

    def by_refresh_hash(self, token_hash: str) -> MobileSession | None:
        return self._find(MobileSessionRecord.refresh_token_hash == token_hash)

    def by_previous_hash(self, token_hash: str) -> MobileSession | None:
        return self._find(MobileSessionRecord.previous_token_hash == token_hash)

    def _find(self, condition) -> MobileSession | None:
        with self._factory() as db:
            return self._to_domain(db.scalars(select(MobileSessionRecord).where(condition).limit(1)).first())

    @staticmethod
    def _to_domain(record: MobileSessionRecord | None) -> MobileSession | None:
        if record is None:
            return None
        return MobileSession(**{name: _aware(getattr(record, name)) for name in _FIELDS})


def _aware(value):
    # SQLite devuelve fechas sin zona; PostgreSQL ya las trae en UTC.
    return value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value
