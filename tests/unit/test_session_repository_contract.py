from __future__ import annotations

import unittest
from datetime import datetime, timezone

from emotv.application import SessionRepository
from emotv.domain import EmotionalSession


class FakeSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, EmotionalSession] = {}

    def save(self, session: EmotionalSession) -> EmotionalSession:
        self.sessions[session.id] = session
        return session

    def get_by_id(self, session_id: str) -> EmotionalSession | None:
        return self.sessions.get(session_id)

    def list_all(self) -> tuple[EmotionalSession, ...]:
        return tuple(self.sessions.values())

    def list_by_student(self, student_id: str) -> tuple[EmotionalSession, ...]:
        return tuple(
            session
            for session in self.sessions.values()
            if session.student_id == student_id
        )


class SessionRepositoryContractTests(unittest.TestCase):
    def test_structural_implementation_satisfies_contract(self) -> None:
        repository = FakeSessionRepository()

        self.assertIsInstance(repository, SessionRepository)

    def test_contract_supports_minimum_session_operations(self) -> None:
        repository: SessionRepository = FakeSessionRepository()
        session = EmotionalSession(
            id="session-001",
            started_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )

        saved = repository.save(session)

        self.assertIs(saved, session)
        self.assertIs(repository.get_by_id(session.id), session)
        self.assertEqual(repository.list_all(), (session,))
        self.assertEqual(repository.list_by_student("student-1"), ())
        self.assertIsNone(repository.get_by_id("missing"))


if __name__ == "__main__":
    unittest.main()
