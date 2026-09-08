from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine

from emotv.application import SessionRepository, SessionService
from emotv.domain import EmotionalSession, SessionState
from emotv.infrastructure.persistence import (
    Base,
    PostgresSessionRepository,
    create_session_factory,
)


class PostgresSessionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.repository = PostgresSessionRepository(
            create_session_factory(self.engine)
        )
        self.started_at = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_implements_repository_contract(self) -> None:
        self.assertIsInstance(self.repository, SessionRepository)

    def test_saves_and_recovers_session(self) -> None:
        session = EmotionalSession("session-001", self.started_at)

        saved = self.repository.save(session)
        recovered = self.repository.get_by_id(session.id)

        self.assertIs(saved, session)
        self.assertEqual(recovered, session)

    def test_returns_none_for_unknown_id(self) -> None:
        self.assertIsNone(self.repository.get_by_id("missing"))

    def test_updates_without_duplicating_session(self) -> None:
        session = EmotionalSession("session-001", self.started_at)
        self.repository.save(session)
        updated = EmotionalSession(
            id=session.id,
            started_at=session.started_at,
            state=SessionState.IN_PROGRESS,
        )

        self.repository.save(updated)

        self.assertEqual(self.repository.get_by_id(session.id), updated)
        self.assertEqual(self.repository.list_all(), (updated,))

    def test_lists_sessions_in_stable_order(self) -> None:
        later = EmotionalSession(
            "session-002",
            self.started_at + timedelta(seconds=1),
        )
        earlier = EmotionalSession("session-001", self.started_at)
        self.repository.save(later)
        self.repository.save(earlier)

        self.assertEqual(self.repository.list_all(), (earlier, later))

    def test_lists_only_sessions_for_student(self) -> None:
        expected = EmotionalSession(
            "session-001",
            self.started_at,
            student_id="student-1",
        )
        another = EmotionalSession(
            "session-002",
            self.started_at + timedelta(seconds=1),
            student_id="student-2",
        )
        self.repository.save(another)
        self.repository.save(expected)

        self.assertEqual(
            self.repository.list_by_student(" student-1 "),
            (expected,),
        )

    def test_rejects_empty_student_id(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.list_by_student(" ")

    def test_lists_only_sessions_for_student(self) -> None:
        first = EmotionalSession(
            "session-001",
            self.started_at,
            student_id="student-1",
        )
        other = EmotionalSession(
            "session-002",
            self.started_at,
            student_id="student-2",
        )
        self.repository.save(first)
        self.repository.save(other)

        self.assertEqual(
            self.repository.list_by_student(" student-1 "),
            (first,),
        )

    def test_operates_with_session_service(self) -> None:
        service = SessionService(
            self.repository,
            clock=lambda: self.started_at,
            id_factory=lambda: "session-service-001",
        )

        started = service.start_session()
        completed = service.complete_session(
            started.id,
            initial_emotion="sadness",
            emotion_confidence=0.81,
            activity_id="arms_up_5s",
            exercise_result="completed",
            exercise_duration_seconds=5.0,
        )

        self.assertIs(completed.state, SessionState.COMPLETED)
        self.assertEqual(service.get_session(completed.id), completed)

    def test_rejects_invalid_values(self) -> None:
        with self.assertRaises(TypeError):
            self.repository.save(object())  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self.repository.get_by_id(" ")


if __name__ == "__main__":
    unittest.main()
