"""Persistencia de auditoría, aceptaciones del compromiso y eliminación de sesiones."""
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
from emotv.infrastructure.persistence.models import (
    AccessAuditRecord,
    CommitmentAcceptanceRecord,
    ExpressionCaptureRecord,
    GuidedRunRecord,
    PracticeResultRecord,
    QuestionnaireResponseRecord,
    ReportCommentRecord,
    ReportEventRecord,
    SessionDeletionRecord,
    SessionMarkerRecord,
    SessionReportRecord,
    SessionRecord,
    VerbalResponseRecord,
)

# Registros de una sesión con session_id, en orden de borrado. Cada tabla nueva
# con datos de una sesión se agrega aquí (o, como los comentarios y el historial
# del reporte, en remaining y _erase) para que la retención y la eliminación la
# incluyan.
SESSION_LINKED_RECORDS = (
    ("questionnaire_responses", QuestionnaireResponseRecord, QuestionnaireResponseRecord.session_id),
    ("expression_captures", ExpressionCaptureRecord, ExpressionCaptureRecord.session_id),
    ("session_markers", SessionMarkerRecord, SessionMarkerRecord.session_id),
    ("verbal_responses", VerbalResponseRecord, VerbalResponseRecord.session_id),
    ("practice_results", PracticeResultRecord, PracticeResultRecord.session_id),
    ("guided_runs", GuidedRunRecord, GuidedRunRecord.session_id),
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


class PostgresSessionErasureRepository:
    """Borra una sesión con todos sus registros y guarda el acta."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    @staticmethod
    def remaining(db: Session, session_id: str) -> dict[str, int]:
        """Registros que siguen asociados a la sesión (debe dar todo cero)."""
        report_ids = select(SessionReportRecord.id).where(SessionReportRecord.session_id == session_id)
        counts = {name: db.scalar(select(func.count()).select_from(model).where(column == session_id))
                  for name, model, column in SESSION_LINKED_RECORDS}
        for name, model in (("report_comments", ReportCommentRecord), ("report_events", ReportEventRecord)):
            counts[name] = db.scalar(select(func.count()).select_from(model).where(model.report_id.in_(report_ids)))
        counts["session_reports"] = db.scalar(select(func.count()).select_from(SessionReportRecord)
                                              .where(SessionReportRecord.session_id == session_id))
        counts["sessions"] = db.scalar(select(func.count()).select_from(SessionRecord)
                                       .where(SessionRecord.id == session_id))
        return counts

    def _erase(self, db: Session, session_id: str) -> tuple[str | None, dict[str, int]]:
        row = db.get(SessionRecord, session_id)
        if row is None:
            raise LookupError(session_id)
        code = row.code
        counts = self.remaining(db, session_id)
        report_ids = select(SessionReportRecord.id).where(SessionReportRecord.session_id == session_id)
        db.execute(delete(ReportCommentRecord).where(ReportCommentRecord.report_id.in_(report_ids)))
        db.execute(delete(ReportEventRecord).where(ReportEventRecord.report_id.in_(report_ids)))
        db.execute(delete(SessionReportRecord).where(SessionReportRecord.session_id == session_id))
        for _, model, column in SESSION_LINKED_RECORDS:
            db.execute(delete(model).where(column == session_id))
        db.execute(delete(SessionRecord).where(SessionRecord.id == session_id))
        db.flush()
        if any(self.remaining(db, session_id).values()):
            # La excepción revierte toda la transacción.
            raise ErasureVerificationError("Quedaron registros asociados a la sesión")
        return code, counts

    def erase(self, session_id: str) -> dict[str, int]:
        with self._factory.begin() as db:
            _, counts = self._erase(db, session_id)
            return counts

    def erase_with_certificate(self, session_id: str, certificate_id: str, deleted_at: datetime,
                               executed_by_user_id: str, requested_by_user_id: str | None) -> DeletionCertificate:
        with self._factory.begin() as db:
            code, counts = self._erase(db, session_id)
            certificate = DeletionCertificate(
                id=certificate_id, session_code=code or "", deleted_at=deleted_at,
                executed_by_user_id=executed_by_user_id, requested_by_user_id=requested_by_user_id,
                counts=counts, verified=True)
            db.add(SessionDeletionRecord(
                id=certificate.id, session_code=certificate.session_code, deleted_at=deleted_at,
                executed_by_user_id=executed_by_user_id, requested_by_user_id=requested_by_user_id,
                counts=counts, verified=True))
        return certificate

    @staticmethod
    def _certificate(row: SessionDeletionRecord) -> DeletionCertificate:
        return DeletionCertificate(id=row.id, session_code=row.session_code, deleted_at=_aware(row.deleted_at),
                                   executed_by_user_id=row.executed_by_user_id,
                                   requested_by_user_id=row.requested_by_user_id,
                                   counts=dict(row.counts), verified=row.verified)

    def get_certificate(self, certificate_id: str) -> DeletionCertificate | None:
        with self._factory() as db:
            row = db.get(SessionDeletionRecord, certificate_id)
            return None if row is None else self._certificate(row)

    def list_certificates_by(self, user_ids: Iterable[str]) -> tuple[DeletionCertificate, ...]:
        ids = tuple(user_ids)
        with self._factory() as db:
            rows = db.scalars(select(SessionDeletionRecord).where(
                SessionDeletionRecord.executed_by_user_id.in_(ids)
                | SessionDeletionRecord.requested_by_user_id.in_(ids))
                .order_by(SessionDeletionRecord.deleted_at.desc())).all()
            return tuple(self._certificate(row) for row in rows)
