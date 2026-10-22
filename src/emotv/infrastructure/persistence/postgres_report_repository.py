"""Persistencia de los reportes: texto y comentarios cifrados, historial sin contenido."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.report import ReportComment, ReportEvent, SessionReport
from emotv.infrastructure.persistence.models import ReportCommentRecord, ReportEventRecord, SessionReportRecord
from emotv.shared.security.field_encryption import FieldCipher


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class PostgresReportRepository:
    def __init__(self, factory: sessionmaker[Session], cipher: FieldCipher) -> None:
        self._factory = factory
        self._cipher = cipher

    def _report(self, row: SessionReportRecord) -> SessionReport:
        return SessionReport(
            id=row.id, family_id=row.family_id, version=row.version, session_id=row.session_id,
            participant_id=row.participant_id, author_user_id=row.author_user_id, status=row.status,
            narrative=self._cipher.decrypt(row.narrative_encrypted) or "", created_at=_aware(row.created_at),
            updated_at=_aware(row.updated_at), approved_at=_aware(row.approved_at),
            approved_by_user_id=row.approved_by_user_id, superseded_at=_aware(row.superseded_at))

    def _fill(self, row: SessionReportRecord, report: SessionReport) -> None:
        row.family_id = report.family_id
        row.version = report.version
        row.session_id = report.session_id
        row.participant_id = report.participant_id
        row.author_user_id = report.author_user_id
        row.status = report.status.value
        row.narrative_encrypted = self._cipher.encrypt(report.narrative or None)
        row.created_at = report.created_at
        row.updated_at = report.updated_at
        row.approved_at = report.approved_at
        row.approved_by_user_id = report.approved_by_user_id
        row.superseded_at = report.superseded_at

    def save(self, report: SessionReport, event: ReportEvent) -> SessionReport:
        """Guarda la versión y su evento del historial en una transacción."""
        with self._factory.begin() as db:
            row = db.get(SessionReportRecord, report.id)
            if row is None:
                row = SessionReportRecord(id=report.id)
                db.add(row)
            self._fill(row, report)
            db.flush()
            self._add_event(db, event, report.participant_id)
        return report

    def add_version(self, previous: SessionReport, report: SessionReport, event: ReportEvent) -> SessionReport:
        with self._factory.begin() as db:
            old = db.get(SessionReportRecord, previous.id)
            if old is None:
                raise LookupError(previous.id)
            old.superseded_at = previous.superseded_at
            row = SessionReportRecord(id=report.id)
            self._fill(row, report)
            db.add(row)
            db.flush()
            self._add_event(db, event, report.participant_id)
        return report

    @staticmethod
    def _add_event(db: Session, event: ReportEvent, participant_id: str) -> None:
        db.add(ReportEventRecord(id=event.id, report_id=event.report_id, participant_id=participant_id,
                                 action=event.action.value, actor_user_id=event.actor_user_id,
                                 occurred_at=event.occurred_at))

    def add_event(self, event: ReportEvent, participant_id: str) -> None:
        with self._factory.begin() as db:
            self._add_event(db, event, participant_id)

    def get(self, report_id: str) -> SessionReport | None:
        with self._factory() as db:
            row = db.get(SessionReportRecord, report_id)
            return None if row is None else self._report(row)

    def list_for_session(self, session_id: str) -> tuple[SessionReport, ...]:
        with self._factory() as db:
            rows = db.scalars(select(SessionReportRecord).where(SessionReportRecord.session_id == session_id)
                              .order_by(SessionReportRecord.version)).all()
            return tuple(self._report(row) for row in rows)

    def add_comment(self, comment: ReportComment, participant_id: str, event: ReportEvent) -> ReportComment:
        with self._factory.begin() as db:
            db.add(ReportCommentRecord(id=comment.id, report_id=comment.report_id, participant_id=participant_id,
                                       section=comment.section.value, text_encrypted=self._cipher.encrypt(comment.text),
                                       author_user_id=comment.author_user_id, created_at=comment.created_at))
            db.flush()
            self._add_event(db, event, participant_id)
        return comment

    def list_comments(self, report_id: str) -> tuple[ReportComment, ...]:
        with self._factory() as db:
            rows = db.scalars(select(ReportCommentRecord).where(ReportCommentRecord.report_id == report_id)
                              .order_by(ReportCommentRecord.created_at, ReportCommentRecord.id)).all()
            return tuple(ReportComment(id=row.id, report_id=row.report_id, section=row.section,
                                       text=self._cipher.decrypt(row.text_encrypted), author_user_id=row.author_user_id,
                                       created_at=_aware(row.created_at)) for row in rows)

    def list_events(self, report_ids: tuple[str, ...]) -> tuple[ReportEvent, ...]:
        if not report_ids:
            return ()
        with self._factory() as db:
            rows = db.scalars(select(ReportEventRecord).where(ReportEventRecord.report_id.in_(report_ids))
                              .order_by(ReportEventRecord.occurred_at, ReportEventRecord.id)).all()
            return tuple(ReportEvent(id=row.id, report_id=row.report_id, action=row.action,
                                     actor_user_id=row.actor_user_id, occurred_at=_aware(row.occurred_at)) for row in rows)
