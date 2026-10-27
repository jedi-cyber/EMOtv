"""Persistencia de los exámenes simulados."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.exam import Exam
from emotv.domain.session import EmotionalSession
from emotv.infrastructure.persistence.models import ExamRecord, SessionRecord
from emotv.infrastructure.persistence.postgres_session_repository import PostgresSessionRepository


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class PostgresExamRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    @staticmethod
    def _domain(row: ExamRecord) -> Exam:
        return Exam(
            id=row.id, owner_user_id=row.owner_user_id, protocol_id=row.protocol_id, join_code=row.join_code,
            created_at=_aware(row.created_at), state=row.state,
            consent_confirmed_at=_aware(row.consent_confirmed_at), started_at=_aware(row.started_at),
            closed_at=_aware(row.closed_at))

    def save(self, exam: Exam) -> Exam:
        with self._factory.begin() as db:
            row = db.get(ExamRecord, exam.id) or ExamRecord(id=exam.id)
            row.owner_user_id = exam.owner_user_id
            row.protocol_id = exam.protocol_id
            row.join_code = exam.join_code
            row.state = exam.state.value
            row.created_at = exam.created_at
            row.consent_confirmed_at = exam.consent_confirmed_at
            row.started_at = exam.started_at
            row.closed_at = exam.closed_at
            db.add(row)
        return exam

    def get(self, exam_id: str) -> Exam | None:
        with self._factory() as db:
            row = db.get(ExamRecord, exam_id)
            return None if row is None else self._domain(row)

    def get_by_join_code(self, join_code: str) -> Exam | None:
        code = (join_code or "").strip().upper()
        with self._factory() as db:
            row = db.scalar(select(ExamRecord).where(ExamRecord.join_code == code))
            return None if row is None else self._domain(row)

    def join_code_exists(self, join_code: str) -> bool:
        with self._factory() as db:
            return db.scalar(select(func.count()).select_from(ExamRecord)
                             .where(ExamRecord.join_code == join_code)) > 0

    def list_by_owner(self, owner_user_id: str) -> tuple[Exam, ...]:
        statement = (select(ExamRecord).where(ExamRecord.owner_user_id == owner_user_id)
                     .order_by(ExamRecord.created_at.desc(), ExamRecord.id))
        with self._factory() as db:
            return tuple(self._domain(row) for row in db.scalars(statement).all())

    def list_sessions(self, exam_id: str) -> tuple[EmotionalSession, ...]:
        """Las sesiones de las estaciones, en el orden en que se unieron."""
        statement = (select(SessionRecord).where(SessionRecord.exam_id == exam_id)
                     .order_by(SessionRecord.started_at, SessionRecord.id))
        with self._factory() as db:
            return tuple(PostgresSessionRepository._to_domain(row) for row in db.scalars(statement).all())
