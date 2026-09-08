from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from emotv.application import SessionRepository, SessionService
from emotv.config import get_database_url
from emotv.domain import EmotionalSession, SessionState
from emotv.infrastructure.persistence import (
    InMemorySessionRepository,
    PostgresSessionRepository,
    create_database_engine,
)


def complete_same_session(
    repository: SessionRepository,
    *,
    session_id: str,
    started_at: datetime,
) -> EmotionalSession:
    """Ejecuta el mismo caso de uso sin conocer el tipo de adaptador."""

    times = iter((started_at, started_at + timedelta(seconds=5)))
    service = SessionService(
        repository,
        clock=lambda: next(times),
        id_factory=lambda: session_id,
    )
    started = service.start_session()
    return service.complete_session(
        started.id,
        initial_emotion="sadness",
        emotion_confidence=0.81,
        activity_id="arms_up_5s",
        exercise_result="completed",
        exercise_duration_seconds=5.0,
    )


@pytest.mark.integration
class RepositoryInterchangeabilityTests(unittest.TestCase):
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

    def test_same_service_behavior_when_only_adapter_changes(self) -> None:
        connection = self.engine.connect()
        transaction = connection.begin()
        try:
            postgres_factory = sessionmaker(
                bind=connection,
                class_=Session,
                autoflush=False,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            memory_repository: SessionRepository = InMemorySessionRepository()
            postgres_repository: SessionRepository = PostgresSessionRepository(
                postgres_factory
            )
            session_id = f"interchangeability-{uuid4()}"
            started_at = datetime.now(timezone.utc)

            memory_result = complete_same_session(
                memory_repository,
                session_id=session_id,
                started_at=started_at,
            )
            postgres_result = complete_same_session(
                postgres_repository,
                session_id=session_id,
                started_at=started_at,
            )

            self.assertEqual(postgres_result, memory_result)
            self.assertIs(postgres_result.state, SessionState.COMPLETED)
            self.assertEqual(
                postgres_repository.get_by_id(session_id),
                memory_repository.get_by_id(session_id),
            )
        finally:
            if transaction.is_active:
                transaction.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()
