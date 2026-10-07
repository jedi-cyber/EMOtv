from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from emotv.infrastructure.persistence.models import LoginAttemptRecord


class PostgresLoginAttemptRepository:
    """Contador de intentos en la base de datos, válido con varios procesos."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def record(self, email_hash: str, ip: str, success: bool, at: datetime, purge_before: datetime) -> None:
        with self._factory.begin() as db:
            db.execute(delete(LoginAttemptRecord).where(LoginAttemptRecord.created_at < purge_before))
            db.add(LoginAttemptRecord(id=str(uuid4()), email_hash=email_hash, ip=ip,
                                      created_at=at, success=success))

    def count_account_failures(self, email_hash: str, ip: str, since: datetime) -> int:
        account = (LoginAttemptRecord.email_hash == email_hash, LoginAttemptRecord.ip == ip)
        with self._factory() as db:
            last_success = db.scalar(select(func.max(LoginAttemptRecord.created_at))
                                     .where(*account, LoginAttemptRecord.success.is_(True),
                                            LoginAttemptRecord.created_at >= since))
            # Un acceso correcto reinicia el contador de esta combinación.
            after = (LoginAttemptRecord.created_at > last_success if last_success is not None
                     else LoginAttemptRecord.created_at >= since)
            return int(db.scalar(select(func.count()).select_from(LoginAttemptRecord).where(
                *account, LoginAttemptRecord.success.is_(False), after)) or 0)

    def count_ip_failures(self, ip: str, since: datetime) -> int:
        with self._factory() as db:
            return int(db.scalar(select(func.count()).select_from(LoginAttemptRecord).where(
                LoginAttemptRecord.ip == ip, LoginAttemptRecord.success.is_(False),
                LoginAttemptRecord.created_at >= since)) or 0)
