from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from emotv.application import SessionRepository
from emotv.domain import EmotionalSession, SessionState
from emotv.infrastructure.persistence import InMemorySessionRepository


class InMemorySessionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemorySessionRepository()
        self.session = EmotionalSession(
            id="session-001",
            started_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )

    def test_implements_session_repository_contract(self) -> None:
        self.assertIsInstance(self.repository, SessionRepository)

    def test_saves_and_recovers_session_by_id(self) -> None:
        saved = self.repository.save(self.session)

        self.assertIs(saved, self.session)
        self.assertIs(self.repository.get_by_id(" session-001 "), self.session)

    def test_returns_none_when_session_does_not_exist(self) -> None:
        self.assertIsNone(self.repository.get_by_id("missing"))

    def test_lists_sessions_in_insertion_order(self) -> None:
        second = EmotionalSession(
            id="session-002",
            started_at=self.session.started_at,
        )
        self.repository.save(self.session)
        self.repository.save(second)

        self.assertEqual(self.repository.list_all(), (self.session, second))

    def test_replaces_same_session_id_without_creating_duplicate(self) -> None:
        self.repository.save(self.session)
        updated = replace(self.session, state=SessionState.IN_PROGRESS)

        self.repository.save(updated)

        self.assertIs(self.repository.get_by_id(self.session.id), updated)
        self.assertEqual(self.repository.list_all(), (updated,))

    def test_rejects_invalid_session(self) -> None:
        with self.assertRaises(TypeError):
            self.repository.save(object())  # type: ignore[arg-type]

    def test_rejects_invalid_session_id(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.get_by_id(" ")
        with self.assertRaises(TypeError):
            self.repository.get_by_id(1)  # type: ignore[arg-type]

    def test_repository_instances_do_not_share_storage(self) -> None:
        self.repository.save(self.session)
        another_repository = InMemorySessionRepository()

        self.assertEqual(another_repository.list_all(), ())


if __name__ == "__main__":
    unittest.main()
