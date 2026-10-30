from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from emotv.domain.audit import AuditEntry


@dataclass(frozen=True, slots=True)
class AuditFilter:
    actor_user_id: str | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None


class AuditRepository(Protocol):
    """Solo agrega y consulta; no existe operación para editar entradas.

    delete_older_than es exclusiva de la tarea de retención."""

    def add(self, entry: AuditEntry) -> None: ...

    def query(self, filters: AuditFilter, limit: int, offset: int) -> tuple[AuditEntry, ...]: ...

    def delete_older_than(self, cutoff: datetime) -> int: ...


class CommitmentRepository(Protocol):
    def has_accepted(self, user_id: str, kind: str, version: str) -> bool: ...

    def add(self, acceptance_id: str, user_id: str, kind: str, version: str, accepted_at: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class DeletionCertificate:
    """Acta de eliminación de una sesión: código, fecha, registros por tipo y
    verificación. Sin datos personales."""

    id: str
    session_code: str
    deleted_at: datetime
    executed_by_user_id: str | None
    requested_by_user_id: str | None
    counts: dict[str, int]
    verified: bool


class SessionErasureRepository(Protocol):
    def erase(self, session_id: str) -> dict[str, int]:
        """Borra la sesión y todos sus registros en una transacción, verifica
        que no quede nada y devuelve la cantidad por tipo. Si la verificación
        falla, revierte y lanza ErasureVerificationError."""
        ...

    def erase_with_certificate(self, session_id: str, certificate_id: str, deleted_at: datetime,
                               executed_by_user_id: str, requested_by_user_id: str | None) -> DeletionCertificate:
        """Como erase, y guarda el acta en la misma transacción."""
        ...

    def get_certificate(self, certificate_id: str) -> DeletionCertificate | None: ...

    def list_certificates_by(self, user_ids: Iterable[str]) -> tuple[DeletionCertificate, ...]: ...


class ErasureVerificationError(RuntimeError):
    """Quedaron registros asociados tras el borrado; se revirtió todo."""
