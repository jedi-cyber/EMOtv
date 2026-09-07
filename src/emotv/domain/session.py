from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from emotv.domain.session_state import SessionState


@dataclass(frozen=True, slots=True)
class EmotionalSession:
    """Registro inmutable del ciclo de una actividad emocional guiada."""

    id: str
    started_at: datetime
    state: SessionState | str = SessionState.CREATED
    completed_at: datetime | None = None
    initial_emotion: str | None = None
    emotion_confidence: float | None = None
    activity_id: str | None = None
    exercise_result: str | None = None
    exercise_duration_seconds: float | None = None

    def __post_init__(self) -> None:
        session_id = self.id.strip()
        if not session_id:
            raise ValueError("id no puede estar vacío")
        if not isinstance(self.started_at, datetime):
            raise TypeError("started_at debe ser datetime")
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("started_at debe incluir zona horaria")

        state = SessionState(self.state) if isinstance(self.state, str) else self.state
        if not isinstance(state, SessionState):
            raise TypeError("state debe ser un SessionState válido")

        if self.completed_at is not None:
            if not isinstance(self.completed_at, datetime):
                raise TypeError("completed_at debe ser datetime")
            if (
                self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None
            ):
                raise ValueError("completed_at debe incluir zona horaria")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at no puede ser anterior a started_at")

        terminal = state in {SessionState.COMPLETED, SessionState.CANCELLED}
        if terminal and self.completed_at is None:
            raise ValueError("una sesión finalizada requiere completed_at")
        if not terminal and self.completed_at is not None:
            raise ValueError("una sesión activa no puede tener completed_at")

        emotion = self._normalize_optional_text(
            self.initial_emotion,
            "initial_emotion",
        )
        activity_id = self._normalize_optional_text(self.activity_id, "activity_id")
        exercise_result = self._normalize_optional_text(
            self.exercise_result,
            "exercise_result",
        )

        if self.emotion_confidence is not None:
            confidence = float(self.emotion_confidence)
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("emotion_confidence debe estar entre 0 y 1")
            object.__setattr__(self, "emotion_confidence", confidence)

        if (emotion is None) != (self.emotion_confidence is None):
            raise ValueError(
                "initial_emotion y emotion_confidence deben registrarse juntos"
            )

        if self.exercise_duration_seconds is not None:
            duration = float(self.exercise_duration_seconds)
            if duration < 0.0:
                raise ValueError("exercise_duration_seconds no puede ser negativa")
            object.__setattr__(self, "exercise_duration_seconds", duration)

        if state is SessionState.COMPLETED:
            required_results = (
                emotion,
                activity_id,
                exercise_result,
                self.exercise_duration_seconds,
            )
            if any(value is None for value in required_results):
                raise ValueError(
                    "una sesión completada requiere emoción, actividad y resultado "
                    "del ejercicio"
                )

        object.__setattr__(self, "id", session_id)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "initial_emotion", emotion)
        object.__setattr__(self, "activity_id", activity_id)
        object.__setattr__(self, "exercise_result", exercise_result)

    @staticmethod
    def _normalize_optional_text(value: str | None, field_name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{field_name} debe ser str")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} no puede estar vacío")
        return normalized.lower()

    @property
    def is_terminal(self) -> bool:
        return self.state in {SessionState.COMPLETED, SessionState.CANCELLED}
