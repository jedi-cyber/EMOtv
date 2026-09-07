from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from emotv.domain import EmotionalSession, SessionState


class EmotionalSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.started_at = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)

    def test_creates_active_session_with_normalized_values(self) -> None:
        session = EmotionalSession(
            id="  session-001  ",
            started_at=self.started_at,
            state="in_progress",
            initial_emotion=" Sadness ",
            emotion_confidence=0.81,
            activity_id=" ARMS_UP_5S ",
        )

        self.assertEqual(session.id, "session-001")
        self.assertIs(session.state, SessionState.IN_PROGRESS)
        self.assertEqual(session.initial_emotion, "sadness")
        self.assertEqual(session.activity_id, "arms_up_5s")
        self.assertFalse(session.is_terminal)

    def test_creates_complete_session(self) -> None:
        session = EmotionalSession(
            id="session-001",
            started_at=self.started_at,
            completed_at=self.started_at + timedelta(seconds=5),
            state=SessionState.COMPLETED,
            initial_emotion="sadness",
            emotion_confidence=0.81,
            activity_id="arms_up_5s",
            exercise_result="completed",
            exercise_duration_seconds=5,
        )

        self.assertTrue(session.is_terminal)
        self.assertEqual(session.exercise_duration_seconds, 5.0)

    def test_creates_cancelled_session_without_exercise_result(self) -> None:
        session = EmotionalSession(
            id="session-001",
            started_at=self.started_at,
            completed_at=self.started_at + timedelta(seconds=2),
            state=SessionState.CANCELLED,
        )

        self.assertTrue(session.is_terminal)

    def test_rejects_empty_id(self) -> None:
        with self.assertRaises(ValueError):
            EmotionalSession(id=" ", started_at=self.started_at)

    def test_requires_timezone_aware_timestamps(self) -> None:
        with self.assertRaises(ValueError):
            EmotionalSession(id="session-001", started_at=datetime(2026, 9, 7))

    def test_rejects_inconsistent_completion_timestamp(self) -> None:
        with self.assertRaises(ValueError):
            EmotionalSession(
                id="session-001",
                started_at=self.started_at,
                state=SessionState.COMPLETED,
            )
        with self.assertRaises(ValueError):
            EmotionalSession(
                id="session-001",
                started_at=self.started_at,
                completed_at=self.started_at,
                state=SessionState.IN_PROGRESS,
            )

    def test_rejects_completion_before_start(self) -> None:
        with self.assertRaises(ValueError):
            EmotionalSession(
                id="session-001",
                started_at=self.started_at,
                completed_at=self.started_at - timedelta(seconds=1),
                state=SessionState.CANCELLED,
            )

    def test_rejects_invalid_emotion_values(self) -> None:
        with self.assertRaises(ValueError):
            EmotionalSession(
                id="session-001",
                started_at=self.started_at,
                initial_emotion="sadness",
            )
        with self.assertRaises(ValueError):
            EmotionalSession(
                id="session-001",
                started_at=self.started_at,
                initial_emotion="sadness",
                emotion_confidence=1.1,
            )

    def test_rejects_negative_exercise_duration(self) -> None:
        with self.assertRaises(ValueError):
            EmotionalSession(
                id="session-001",
                started_at=self.started_at,
                exercise_duration_seconds=-0.1,
            )

    def test_completed_session_requires_complete_result(self) -> None:
        with self.assertRaises(ValueError):
            EmotionalSession(
                id="session-001",
                started_at=self.started_at,
                completed_at=self.started_at,
                state=SessionState.COMPLETED,
                initial_emotion="sadness",
                emotion_confidence=0.81,
            )

    def test_is_immutable(self) -> None:
        session = EmotionalSession(id="session-001", started_at=self.started_at)

        with self.assertRaises(FrozenInstanceError):
            session.state = SessionState.IN_PROGRESS  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
