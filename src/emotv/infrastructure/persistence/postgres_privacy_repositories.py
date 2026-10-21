"""Persistencia de auditoría, aceptaciones del compromiso y participantes."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from emotv.application.ports.privacy_repositories import (
    AuditFilter,
    DeletionCertificate,
    ErasureVerificationError,
)
from emotv.domain.audit import AuditEntry
from emotv.domain.participant import Participant
from emotv.infrastructure.persistence.models import (
    AccessAuditRecord,
    CommitmentAcceptanceRecord,
    ParticipantDeletionRecord,
    ParticipantRecord,
    SessionRecord,
)
from emotv.shared.security.field_encryption import FieldCipher

# Registros vinculados a un participante, en orden de borrado. Cada tabla nueva
# con datos de participantes (autorizaciones, capturas, respuestas, marcadores,
# reportes) se agrega aquí para que la retención y la eliminación la incluyan.
PARTICIPANT_LINKED_RECORDS = (
    ("sessions", SessionRecord, SessionRecord.participant_id),
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class PostgresAuditRepository:
    """Solo agrega y consulta; delete_older_than es exclusiva de la retención."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def add(self, entry: AuditEntry) -> None:
        with self._factory.begin() as db:
            db.add(AccessAuditRecord(
                id=entry.id, occurred_at=entry.occurred_at, actor_user_id=entry.actor_user_id,
                actor_role=entry.actor_role, action=entry.action.value, resource_type=entry.resource_type,
                resource_id=entry.resource_id, result=entry.result.value))

    def query(self, filters: AuditFilter, limit: int, offset: int) -> tuple[AuditEntry, ...]:
        statement = select(AccessAuditRecord)
        for column, value in ((AccessAuditRecord.actor_user_id, filters.actor_user_id),
                              (AccessAuditRecord.action, filters.action),
                              (AccessAuditRecord.resource_type, filters.resource_type),
                              (AccessAuditRecord.resource_id, filters.resource_id)):
            if value:
                statement = statement.where(column == value)
        if filters.since is not None:
            statement = statement.where(AccessAuditRecord.occurred_at >= filters.since)
        if filters.until is not None:
            statement = statement.where(AccessAuditRecord.occurred_at <= filters.until)
        statement = statement.order_by(AccessAuditRecord.occurred_at.desc(), AccessAuditRecord.id)
        with self._factory() as db:
            rows = db.scalars(statement.limit(limit).offset(offset)).all()
            return tuple(AuditEntry(id=row.id, occurred_at=_aware(row.occurred_at), actor_user_id=row.actor_user_id,
                                    actor_role=row.actor_role, action=row.action, resource_type=row.resource_type,
                                    resource_id=row.resource_id, result=row.result) for row in rows)

    def delete_older_than(self, cutoff: datetime) -> int:
        with self._factory.begin() as db:
            return db.execute(delete(AccessAuditRecord).where(AccessAuditRecord.occurred_at < cutoff)).rowcount or 0


class PostgresCommitmentRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def has_accepted(self, user_id: str, kind: str, version: str) -> bool:
        with self._factory() as db:
            return db.scalar(select(func.count()).select_from(CommitmentAcceptanceRecord).where(
                CommitmentAcceptanceRecord.user_id == user_id, CommitmentAcceptanceRecord.kind == kind,
                CommitmentAcceptanceRecord.version == version)) > 0

    def add(self, acceptance_id: str, user_id: str, kind: str, version: str, accepted_at: datetime) -> None:
        with self._factory.begin() as db:
            db.add(CommitmentAcceptanceRecord(id=acceptance_id, user_id=user_id, kind=kind, version=version,
                                              accepted_at=accepted_at))


class PostgresParticipantRepository:
    """Las notas se cifran antes de llegar a la base y se descifran al leer."""

    def __init__(self, factory: sessionmaker[Session], cipher: FieldCipher) -> None:
        self._factory = factory
        self._cipher = cipher

    def save(self, participant: Participant) -> Participant:
        with self._factory.begin() as db:
            row = db.get(ParticipantRecord, participant.id)
            if row is None:
                row = ParticipantRecord(id=participant.id)
                db.add(row)
            row.code = participant.code
            row.kind = participant.kind.value
            row.registered_by_user_id = participant.registered_by_user_id
            row.created_at = participant.created_at
            row.notes_encrypted = self._cipher.encrypt(participant.notes)
            row.deletion_requested_at = participant.deletion_requested_at
            row.deletion_requested_by_user_id = participant.deletion_requested_by_user_id
        return participant

    def _domain(self, row: ParticipantRecord) -> Participant:
        return Participant(id=row.id, code=row.code, kind=row.kind, registered_by_user_id=row.registered_by_user_id,
                           created_at=_aware(row.created_at), notes=self._cipher.decrypt(row.notes_encrypted),
                           deletion_requested_at=_aware(row.deletion_requested_at),
                           deletion_requested_by_user_id=row.deletion_requested_by_user_id)

    def get_by_id(self, participant_id: str) -> Participant | None:
        with self._factory() as db:
            row = db.get(ParticipantRecord, participant_id)
            return None if row is None else self._domain(row)

    def code_exists(self, code: str) -> bool:
        with self._factory() as db:
            return db.scalar(select(func.count()).select_from(ParticipantRecord)
                             .where(ParticipantRecord.code == code)) > 0

    def list_by_registrants(self, user_ids: Iterable[str]) -> tuple[Participant, ...]:
        ids = tuple(user_ids)
        if not ids:
            return ()
        with self._factory() as db:
            rows = db.scalars(select(ParticipantRecord).where(ParticipantRecord.registered_by_user_id.in_(ids))
                              .order_by(ParticipantRecord.created_at, ParticipantRecord.id)).all()
            return tuple(self._domain(row) for row in rows)

    def list_created_before(self, cutoff: datetime) -> tuple[Participant, ...]:
        with self._factory() as db:
            rows = db.scalars(select(ParticipantRecord).where(ParticipantRecord.created_at < cutoff)).all()
            return tuple(self._domain(row) for row in rows)

    @staticmethod
    def remaining(db: Session, participant_id: str) -> dict[str, int]:
        """Registros que siguen asociados al participante (debe dar todo cero)."""
        counts = {name: db.scalar(select(func.count()).select_from(model).where(column == participant_id))
                  for name, model, column in PARTICIPANT_LINKED_RECORDS}
        counts["participants"] = db.scalar(select(func.count()).select_from(ParticipantRecord)
                                           .where(ParticipantRecord.id == participant_id))
        return counts

    def _erase(self, db: Session, participant_id: str) -> tuple[ParticipantRecord, dict[str, int]]:
        row = db.get(ParticipantRecord, participant_id)
        if row is None:
            raise LookupError(participant_id)
        counts = self.remaining(db, participant_id)
        for _, model, column in PARTICIPANT_LINKED_RECORDS:
            db.execute(delete(model).where(column == participant_id))
        db.execute(delete(ParticipantRecord).where(ParticipantRecord.id == participant_id))
        db.flush()
        if any(self.remaining(db, participant_id).values()):
            # La excepción revierte toda la transacción.
            raise ErasureVerificationError("Quedaron registros asociados al participante")
        return row, counts

    def erase(self, participant_id: str) -> dict[str, int]:
        with self._factory.begin() as db:
            _, counts = self._erase(db, participant_id)
            return counts

    def erase_with_certificate(self, participant_id: str, certificate_id: str, deleted_at: datetime,
                               executed_by_user_id: str, requested_by_user_id: str | None) -> DeletionCertificate:
        with self._factory.begin() as db:
            row, counts = self._erase(db, participant_id)
            certificate = DeletionCertificate(
                id=certificate_id, participant_code=row.code, deleted_at=deleted_at,
                executed_by_user_id=executed_by_user_id, requested_by_user_id=requested_by_user_id,
                counts=counts, verified=True)
            db.add(ParticipantDeletionRecord(
                id=certificate.id, participant_code=certificate.participant_code, deleted_at=deleted_at,
                executed_by_user_id=executed_by_user_id, requested_by_user_id=requested_by_user_id,
                counts=counts, verified=True))
        return certificate

    @staticmethod
    def _certificate(row: ParticipantDeletionRecord) -> DeletionCertificate:
        return DeletionCertificate(id=row.id, participant_code=row.participant_code, deleted_at=_aware(row.deleted_at),
                                   executed_by_user_id=row.executed_by_user_id,
                                   requested_by_user_id=row.requested_by_user_id,
                                   counts=dict(row.counts), verified=row.verified)

    def get_certificate(self, certificate_id: str) -> DeletionCertificate | None:
        with self._factory() as db:
            row = db.get(ParticipantDeletionRecord, certificate_id)
            return None if row is None else self._certificate(row)

    def list_certificates_by(self, user_ids: Iterable[str]) -> tuple[DeletionCertificate, ...]:
        ids = tuple(user_ids)
        with self._factory() as db:
            rows = db.scalars(select(ParticipantDeletionRecord).where(
                ParticipantDeletionRecord.executed_by_user_id.in_(ids)
                | ParticipantDeletionRecord.requested_by_user_id.in_(ids))
                .order_by(ParticipantDeletionRecord.deleted_at.desc())).all()
            return tuple(self._certificate(row) for row in rows)
