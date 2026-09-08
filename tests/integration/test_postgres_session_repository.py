from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from emotv.application import SessionService
from emotv.config import get_database_url
from emotv.domain import EmotionalSession, SessionState
from emotv.domain import ConsentRecord, Role, Student, User
from emotv.infrastructure.persistence import (
    PostgresConsentRepository,
    PostgresStudentRepository,
    PostgresUserRepository,
    PostgresSessionRepository,
    create_database_engine,
)


@pytest.mark.integration
class PostgresSessionRepositoryIntegrationTests(unittest.TestCase):
    engine: Engine

    @classmethod
    def setUpClass(cls) -> None:
        try:
            database_url = get_database_url()
        except RuntimeError as error:
            raise unittest.SkipTest(str(error)) from error

        cls.engine = create_database_engine(database_url)
        with cls.engine.connect() as connection:
            if "sessions" not in inspect(connection).get_table_names():
                cls.engine.dispose()
                raise RuntimeError(
                    "Falta la tabla sessions. Ejecuta: python -m alembic upgrade head"
                )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def setUp(self) -> None:
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        factory = sessionmaker(
            bind=self.connection,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.repository = PostgresSessionRepository(factory)
        self.user_repository = PostgresUserRepository(factory)
        self.student_repository = PostgresStudentRepository(factory)
        self.consent_repository = PostgresConsentRepository(factory)
        self.started_at = datetime.now(timezone.utc)

    def tearDown(self) -> None:
        if self.transaction.is_active:
            self.transaction.rollback()
        self.connection.close()

    def test_persists_updates_and_recovers_real_postgres_session(self) -> None:
        session_id = f"integration-{uuid4()}"
        started = EmotionalSession(
            id=session_id,
            started_at=self.started_at,
            state=SessionState.IN_PROGRESS,
        )
        self.repository.save(started)
        completed = EmotionalSession(
            id=session_id,
            started_at=self.started_at,
            completed_at=self.started_at + timedelta(seconds=5),
            state=SessionState.COMPLETED,
            initial_emotion="sadness",
            emotion_confidence=0.81,
            activity_id="arms_up_5s",
            exercise_result="completed",
            exercise_duration_seconds=5.0,
        )

        self.repository.save(completed)
        recovered = self.repository.get_by_id(session_id)

        self.assertEqual(recovered, completed)
        self.assertEqual(
            [item for item in self.repository.list_all() if item.id == session_id],
            [completed],
        )

    def test_session_service_works_with_real_postgres_repository(self) -> None:
        session_id = f"integration-{uuid4()}"
        completed_at = self.started_at + timedelta(seconds=5)
        times = iter((self.started_at, completed_at))
        service = SessionService(
            self.repository,
            clock=lambda: next(times),
            id_factory=lambda: session_id,
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

        self.assertEqual(service.get_session(session_id), completed)
        self.assertIs(completed.state, SessionState.COMPLETED)

    def test_changes_are_visible_inside_test_transaction(self) -> None:
        session = EmotionalSession(
            id=f"integration-{uuid4()}",
            started_at=self.started_at,
        )

        self.repository.save(session)

        self.assertEqual(self.repository.get_by_id(session.id), session)

    def test_database_rejects_invalid_confidence(self) -> None:
        with self.assertRaises(IntegrityError):
            with self.connection.begin_nested():
                self.connection.execute(
                    text(
                        "INSERT INTO sessions "
                        "(id, state, started_at, initial_emotion, "
                        "emotion_confidence) "
                        "VALUES (:id, 'in_progress', :started_at, "
                        "'sadness', 1.5)"
                    ),
                    {
                        "id": f"integration-{uuid4()}",
                        "started_at": self.started_at,
                    },
                )

    def test_identity_repositories_use_real_postgres(self) -> None:
        suffix = str(uuid4())
        user = User(f"user-{suffix}", f"{suffix}@example.com", "argon-hash",
                    Role.STUDENT, self.started_at)
        student = Student(f"student-{suffix}", user.id, f"code-{suffix}")
        consent = ConsentRecord(f"consent-{suffix}", student.id,
                                "privacy-v1", self.started_at)

        self.user_repository.save(user)
        self.student_repository.save(student)
        self.consent_repository.save(consent)

        self.assertEqual(self.user_repository.get_by_email(user.email), user)
        self.assertEqual(self.student_repository.get_by_user_id(user.id), student)
        self.assertEqual(
            self.consent_repository.get_active_by_student(student.id), consent
        )


if __name__ == "__main__":
    unittest.main()
