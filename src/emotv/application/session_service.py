from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from emotv.application.ports.session_repository import SessionRepository
from emotv.application.ports.consent_repository import ConsentRepository
from emotv.domain.emotional_activity_status import EmotionalActivityStatus
from emotv.domain.session import EmotionalSession
from emotv.domain.session_state import SessionState


Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


class SessionService:
    """Administra el ciclo de vida de las sesiones sin conocer su persistencia."""

    def __init__(
        self,
        repository: SessionRepository,
        clock: Clock | None = None,
        id_factory: IdFactory | None = None,
        consent_repository: ConsentRepository | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: str(uuid4()))
        self.consent_repository = consent_repository

    def create_session(self, student_id: str | None = None) -> EmotionalSession:
        """Crea y guarda una sesión que todavía no ha comenzado."""

        session = EmotionalSession(
            id=self._next_unique_id(),
            started_at=self.clock(),
            state=SessionState.CREATED,
            student_id=student_id,
        )
        return self.repository.save(session)

    def start_session(
        self,
        session_id: str | None = None,
        student_id: str | None = None,
    ) -> EmotionalSession:
        """Inicia una sesión nueva o una sesión previamente creada."""

        if session_id is None:
            self._require_active_consent(student_id)
            session = EmotionalSession(
                id=self._next_unique_id(),
                started_at=self.clock(),
                state=SessionState.IN_PROGRESS,
                student_id=student_id,
            )
        else:
            current = self._get_required(session_id)
            if student_id is not None and student_id.strip() != current.student_id:
                raise ValueError("student_id no coincide con la sesión creada")
            self._require_active_consent(current.student_id)
            self._require_state(current, SessionState.CREATED, "iniciar")
            session = replace(
                current,
                state=SessionState.IN_PROGRESS,
                started_at=self.clock(),
            )
        return self.repository.save(session)

    def _require_active_consent(self, student_id: str | None) -> None:
        if student_id is None:
            return
        normalized_id = student_id.strip()
        if not normalized_id:
            raise ValueError("student_id no puede estar vacío")
        if self.consent_repository is None:
            raise RuntimeError(
                "se requiere ConsentRepository para iniciar una sesión asociada"
            )
        if self.consent_repository.get_active_by_student(normalized_id) is None:
            raise PermissionError(
                "el estudiante no tiene un consentimiento activo"
            )

    def complete_session(
        self,
        session_id: str,
        *,
        initial_emotion: str,
        emotion_confidence: float,
        activity_id: str,
        exercise_result: str,
        exercise_duration_seconds: float,
    ) -> EmotionalSession:
        """Completa y guarda una sesión con el resultado íntegro del MVP."""

        current = self._get_required(session_id)
        self._require_state(current, SessionState.IN_PROGRESS, "completar")
        completed = replace(
            current,
            state=SessionState.COMPLETED,
            completed_at=self.clock(),
            initial_emotion=initial_emotion,
            emotion_confidence=emotion_confidence,
            activity_id=activity_id,
            exercise_result=exercise_result,
            exercise_duration_seconds=exercise_duration_seconds,
        )
        return self.repository.save(completed)

    def complete_from_activity_status(
        self,
        session_id: str,
        status: EmotionalActivityStatus,
    ) -> EmotionalSession:
        """Completa una sesión usando el resultado final del flujo inteligente."""

        if not isinstance(status, EmotionalActivityStatus):
            raise TypeError("status debe ser un EmotionalActivityStatus")
        if not status.completed:
            raise ValueError("el flujo emocional todavía no está completado")
        if status.emotion is None or status.activity is None or status.exercise is None:
            raise ValueError("el resultado emocional completado está incompleto")

        return self.complete_session(
            session_id,
            initial_emotion=status.emotion.emotion,
            emotion_confidence=status.emotion.confidence,
            activity_id=status.activity.id,
            exercise_result=status.exercise.state.value,
            exercise_duration_seconds=status.exercise.elapsed_seconds,
        )

    def cancel_session(self, session_id: str) -> EmotionalSession:
        """Cancela y guarda una sesión creada o en progreso."""

        current = self._get_required(session_id)
        if current.state not in {SessionState.CREATED, SessionState.IN_PROGRESS}:
            raise RuntimeError(
                f"No se puede cancelar una sesión en estado {current.state.value}"
            )
        cancelled = replace(
            current,
            state=SessionState.CANCELLED,
            completed_at=self.clock(),
        )
        return self.repository.save(cancelled)

    def get_session(self, session_id: str) -> EmotionalSession | None:
        return self.repository.get_by_id(session_id)

    def list_sessions(self) -> tuple[EmotionalSession, ...]:
        return self.repository.list_all()

    def list_sessions_by_student(
        self,
        student_id: str,
    ) -> tuple[EmotionalSession, ...]:
        """Consulta exclusivamente las sesiones asociadas a un estudiante."""

        return self.repository.list_by_student(student_id)

    def _get_required(self, session_id: str) -> EmotionalSession:
        normalized_id = session_id.strip()
        if not normalized_id:
            raise ValueError("session_id no puede estar vacío")
        session = self.repository.get_by_id(normalized_id)
        if session is None:
            raise KeyError(f"Sesión no encontrada: {normalized_id}")
        return session

    @staticmethod
    def _require_state(
        session: EmotionalSession,
        expected: SessionState,
        operation: str,
    ) -> None:
        if session.state is not expected:
            raise RuntimeError(
                f"No se puede {operation} una sesión en estado {session.state.value}"
            )

    def _next_unique_id(self) -> str:
        for _ in range(100):
            candidate = self.id_factory().strip()
            if not candidate:
                raise ValueError("id_factory generó un ID vacío")
            if self.repository.get_by_id(candidate) is None:
                return candidate
        raise RuntimeError("No se pudo generar un ID de sesión único")
