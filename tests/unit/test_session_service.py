from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from emotv.application import SessionService
from emotv.domain import (
    Activity,
    EmotionalActivityState,
    EmotionalActivityStatus,
    EmotionalSession,
    ExerciseState,
    ExerciseStatus,
    PostureId,
    SessionState,
    StabilizedEmotion,
    ConsentRecord,
)


class FakeRepository:
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


class FakeClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class FakeConsentRepository:
    def __init__(self, active: ConsentRecord | None = None) -> None:
        self.active = active

    def save(self, consent: ConsentRecord) -> ConsentRecord:
        self.active = consent
        return consent

    def get_by_id(self, consent_id: str) -> ConsentRecord | None:
        return self.active if self.active and self.active.id == consent_id else None

    def list_by_student(self, student_id: str) -> tuple[ConsentRecord, ...]:
        return (self.active,) if self.active and self.active.student_id == student_id else ()

    def get_active_by_student(self, student_id: str) -> ConsentRecord | None:
        if self.active and self.active.student_id == student_id and self.active.is_active:
            return self.active
        return None


class SessionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.started_at = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
        self.clock = FakeClock(self.started_at)
        self.service = SessionService(
            self.repository,
            clock=self.clock,
            id_factory=lambda: "session-001",
        )

    def test_creates_session(self) -> None:
        session = self.service.create_session()

        self.assertIs(session.state, SessionState.CREATED)
        self.assertIs(self.service.get_session(session.id), session)

    def test_starts_new_session(self) -> None:
        session = self.service.start_session()

        self.assertIs(session.state, SessionState.IN_PROGRESS)
        self.assertEqual(session.started_at, self.started_at)

    def test_starts_previously_created_session(self) -> None:
        created = self.service.create_session()
        self.clock.value += timedelta(seconds=1)

        started = self.service.start_session(created.id)

        self.assertIs(started.state, SessionState.IN_PROGRESS)
        self.assertEqual(started.started_at, self.clock.value)

    def test_completes_session_with_mvp_result(self) -> None:
        started = self.service.start_session()
        self.clock.value += timedelta(seconds=5)

        completed = self.service.complete_session(
            started.id,
            initial_emotion="sadness",
            emotion_confidence=0.81,
            activity_id="arms_up_5s",
            exercise_result="completed",
            exercise_duration_seconds=5.0,
        )

        self.assertIs(completed.state, SessionState.COMPLETED)
        self.assertEqual(completed.completed_at, self.clock.value)
        self.assertEqual(completed.activity_id, "arms_up_5s")
        self.assertIs(self.service.get_session(completed.id), completed)

    def test_cancels_created_or_started_session(self) -> None:
        created = self.service.create_session()
        cancelled = self.service.cancel_session(created.id)

        self.assertIs(cancelled.state, SessionState.CANCELLED)
        self.assertEqual(cancelled.completed_at, self.started_at)

    def test_completes_session_from_emotional_activity_result(self) -> None:
        started = self.service.start_session()
        status = EmotionalActivityStatus(
            state=EmotionalActivityState.COMPLETED,
            message="Actividad completada",
            emotion=StabilizedEmotion("sadness", 0.81, 0.8, 4, 5),
            activity=Activity(
                id="arms_up_5s",
                name="Brazos arriba",
                description="Mantén ambos brazos arriba",
                required_posture=PostureId.ARMS_UP,
                duration_seconds=5.0,
            ),
            exercise=ExerciseStatus(ExerciseState.COMPLETED, 1.0, 5.0),
        )

        completed = self.service.complete_from_activity_status(started.id, status)

        self.assertIs(completed.state, SessionState.COMPLETED)
        self.assertEqual(completed.initial_emotion, "sadness")
        self.assertEqual(completed.emotion_confidence, 0.81)
        self.assertEqual(completed.activity_id, "arms_up_5s")
        self.assertEqual(completed.exercise_result, "completed")
        self.assertEqual(completed.exercise_duration_seconds, 5.0)

    def test_rejects_incomplete_emotional_activity_result(self) -> None:
        started = self.service.start_session()
        status = EmotionalActivityStatus(
            state=EmotionalActivityState.ANALYZING_EMOTION,
            message="Analizando",
        )

        with self.assertRaises(ValueError):
            self.service.complete_from_activity_status(started.id, status)

    def test_rejects_unknown_session(self) -> None:
        with self.assertRaises(KeyError):
            self.service.cancel_session("missing")

    def test_rejects_invalid_or_repeated_transitions(self) -> None:
        started = self.service.start_session()
        completed = self.service.complete_session(
            started.id,
            initial_emotion="sadness",
            emotion_confidence=0.81,
            activity_id="arms_up_5s",
            exercise_result="completed",
            exercise_duration_seconds=5.0,
        )

        with self.assertRaises(RuntimeError):
            self.service.complete_session(
                completed.id,
                initial_emotion="sadness",
                emotion_confidence=0.81,
                activity_id="arms_up_5s",
                exercise_result="completed",
                exercise_duration_seconds=5.0,
            )
        with self.assertRaises(RuntimeError):
            self.service.cancel_session(completed.id)

    def test_lists_sessions_through_repository(self) -> None:
        session = self.service.start_session()

        self.assertEqual(self.service.list_sessions(), (session,))

    def test_lists_sessions_by_student_through_repository(self) -> None:
        first = EmotionalSession(
            "student-session",
            self.started_at,
            student_id="student-1",
        )
        other = EmotionalSession(
            "other-session",
            self.started_at,
            student_id="student-2",
        )
        self.repository.save(first)
        self.repository.save(other)

        self.assertEqual(
            self.service.list_sessions_by_student("student-1"),
            (first,),
        )

    def test_avoids_duplicate_ids(self) -> None:
        ids = iter(("duplicate", "duplicate", "unique"))
        service = SessionService(
            self.repository,
            clock=self.clock,
            id_factory=lambda: next(ids),
        )

        first = service.start_session()
        second = service.start_session()

        self.assertEqual(first.id, "duplicate")
        self.assertEqual(second.id, "unique")

    def test_requires_active_consent_for_associated_session(self) -> None:
        consent = ConsentRecord(
            "consent-1", "student-1", "privacy-v1", self.started_at
        )
        service = SessionService(
            self.repository,
            clock=self.clock,
            id_factory=lambda: "associated-session",
            consent_repository=FakeConsentRepository(consent),
        )

        session = service.start_session(student_id="student-1")

        self.assertEqual(session.student_id, "student-1")

    def test_rejects_associated_session_without_active_consent(self) -> None:
        for consents in (None, FakeConsentRepository()):
            with self.subTest(consents=consents):
                service = SessionService(
                    self.repository,
                    clock=self.clock,
                    id_factory=lambda: "associated-session",
                    consent_repository=consents,
                )
                with self.assertRaises((RuntimeError, PermissionError)):
                    service.start_session(student_id="student-1")

    def test_revalidates_consent_when_starting_created_session(self) -> None:
        service = SessionService(
            self.repository,
            clock=self.clock,
            id_factory=lambda: "created-associated",
            consent_repository=FakeConsentRepository(),
        )
        created = service.create_session(student_id="student-1")

        with self.assertRaises(PermissionError):
            service.start_session(created.id)


if __name__ == "__main__":
    unittest.main()
