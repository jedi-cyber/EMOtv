from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.session import EmotionalSession
from emotv.domain.session_state import SessionState
from emotv.infrastructure.persistence.models import SessionRecord


class PostgresSessionRepository:
    """Persistencia SQLAlchemy de sesiones para PostgreSQL."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory debe ser invocable")
        self._session_factory = session_factory

    def save(self, session: EmotionalSession) -> EmotionalSession:
        if not isinstance(session, EmotionalSession):
            raise TypeError("session debe ser una EmotionalSession")

        with self._session_factory.begin() as database_session:
            record = database_session.get(SessionRecord, session.id)
            if record is None:
                database_session.add(self._to_record(session))
            else:
                self._update_record(record, session)
        return session

    def get_by_id(self, session_id: str) -> EmotionalSession | None:
        normalized_id = self._normalize_id(session_id)
        with self._session_factory() as database_session:
            record = database_session.get(SessionRecord, normalized_id)
            return None if record is None else self._to_domain(record)

    def list_all(self) -> tuple[EmotionalSession, ...]:
        statement = select(SessionRecord).order_by(
            SessionRecord.started_at,
            SessionRecord.id,
        )
        with self._session_factory() as database_session:
            records = database_session.scalars(statement).all()
            return tuple(self._to_domain(record) for record in records)

    def list_by_student(self, student_id: str) -> tuple[EmotionalSession, ...]:
        normalized_id = self._normalize_student_id(student_id)
        statement = (
            select(SessionRecord)
            .where(SessionRecord.student_id == normalized_id)
            .order_by(SessionRecord.started_at, SessionRecord.id)
        )
        with self._session_factory() as database_session:
            records = database_session.scalars(statement).all()
            return tuple(self._to_domain(record) for record in records)

    @staticmethod
    def _to_record(session: EmotionalSession) -> SessionRecord:
        return SessionRecord(
            id=session.id,
            state=session.state.value,
            started_at=session.started_at,
            completed_at=session.completed_at,
            initial_emotion=session.initial_emotion,
            emotion_confidence=session.emotion_confidence,
            activity_id=session.activity_id,
            exercise_result=session.exercise_result,
            exercise_duration_seconds=session.exercise_duration_seconds,
            student_id=session.student_id,
        )

    @staticmethod
    def _update_record(
        record: SessionRecord,
        session: EmotionalSession,
    ) -> None:
        record.state = session.state.value
        record.started_at = session.started_at
        record.completed_at = session.completed_at
        record.initial_emotion = session.initial_emotion
        record.emotion_confidence = session.emotion_confidence
        record.activity_id = session.activity_id
        record.exercise_result = session.exercise_result
        record.exercise_duration_seconds = session.exercise_duration_seconds
        record.student_id = session.student_id

    @classmethod
    def _to_domain(cls, record: SessionRecord) -> EmotionalSession:
        return EmotionalSession(
            id=record.id,
            state=SessionState(record.state),
            started_at=cls._as_aware(record.started_at),
            completed_at=(
                cls._as_aware(record.completed_at)
                if record.completed_at is not None
                else None
            ),
            initial_emotion=record.initial_emotion,
            emotion_confidence=record.emotion_confidence,
            activity_id=record.activity_id,
            exercise_result=record.exercise_result,
            exercise_duration_seconds=record.exercise_duration_seconds,
            student_id=record.student_id,
        )

    @staticmethod
    def _as_aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _normalize_id(session_id: str) -> str:
        if not isinstance(session_id, str):
            raise TypeError("session_id debe ser str")
        normalized_id = session_id.strip()
        if not normalized_id:
            raise ValueError("session_id no puede estar vacío")
        return normalized_id

    @staticmethod
    def _normalize_student_id(student_id: str) -> str:
        if not isinstance(student_id, str):
            raise TypeError("student_id debe ser str")
        normalized_id = student_id.strip()
        if not normalized_id:
            raise ValueError("student_id no puede estar vacío")
        return normalized_id
