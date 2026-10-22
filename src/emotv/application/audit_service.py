"""Auditoría de accesos: quién hizo qué, sobre qué recurso y con qué resultado.

Nunca guarda contenido (notas, respuestas, correos) ni imágenes. La API solo
la consulta; la única eliminación es la de la retención (AUDIT_RETENTION_MONTHS).
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4

from emotv.application.ports.privacy_repositories import AuditFilter, AuditRepository
from emotv.domain.audit import AuditAction, AuditEntry, AuditResult
from emotv.domain.user import User

logger = logging.getLogger(__name__)
DAYS_PER_MONTH = 30


def months_ago(now: datetime, months: int) -> datetime:
    return now - timedelta(days=months * DAYS_PER_MONTH)


class AuditService:
    def __init__(self, repository: AuditRepository, clock: Callable[[], datetime] | None = None) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def record(
        self,
        actor: User | None,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        result: AuditResult = AuditResult.SUCCESS,
    ) -> None:
        self.repository.add(AuditEntry(
            id=str(uuid4()), occurred_at=self.clock(),
            actor_user_id=actor.id if actor else None,
            actor_role=actor.role.value if actor else None,
            action=action, resource_type=resource_type, resource_id=resource_id, result=result,
        ))

    def query(self, filters: AuditFilter, limit: int = 100, offset: int = 0) -> tuple[AuditEntry, ...]:
        return self.repository.query(filters, max(1, min(limit, 500)), max(0, offset))

    def purge_expired(self, retention_months: int) -> int:
        removed = self.repository.delete_older_than(months_ago(self.clock(), retention_months))
        if removed:
            logger.info("Retención de auditoría: %s entradas eliminadas", removed)
        return removed
