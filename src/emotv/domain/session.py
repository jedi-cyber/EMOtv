from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from emotv.domain.session_state import ActivityOutcome, SessionState


@dataclass(frozen=True, slots=True)
class EmotionalSession:
    """Registro inmutable del ciclo de una actividad emocional guiada.

    recognized_at marca la expresión elegida por el estudiante en el análisis
    en vivo; es nulo en sesiones anteriores a ese flujo o sin confirmación.
    """

    id: str
    started_at: datetime
    state: SessionState | str = SessionState.CREATED
    completed_at: datetime | None = None
    initial_emotion: str | None = None
    emotion_confidence: float | None = None
    activity_id: str | None = None
    exercise_result: str | None = None
    exercise_duration_seconds: float | None = None
    student_id: str | None = None
    emotion_model_id: str | None = None
    emotion_model_version: str | None = None
    recognized_at: datetime | None = None
    # Avance de una actividad secuencial: pasos completados de un total de
    # pasos × repeticiones. Se guarda en cada cambio de paso, así una sesión
    # interrumpida conserva hasta dónde llegó.
    exercise_steps_completed: int | None = None
    exercise_steps_total: int | None = None
    exercise_repetitions: int | None = None

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
        student_id = self._normalize_optional_text(self.student_id, "student_id")
        model_id = self._normalize_optional_text(self.emotion_model_id, "emotion_model_id")
        model_version = self.emotion_model_version
        if model_version is not None:
            if not isinstance(model_version, str):
                raise TypeError("emotion_model_version debe ser str")
            model_version = model_version.strip()
            if not model_version:
                raise ValueError("emotion_model_version no puede estar vacío")
        if (model_id is None) != (model_version is None):
            raise ValueError("emotion_model_id y emotion_model_version deben registrarse juntos")

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

        self._validate_progress()

        if self.recognized_at is not None:
            if not isinstance(self.recognized_at, datetime):
                raise TypeError("recognized_at debe ser datetime")
            if self.recognized_at.tzinfo is None or self.recognized_at.utcoffset() is None:
                raise ValueError("recognized_at debe incluir zona horaria")
            if self.recognized_at < self.started_at:
                raise ValueError("recognized_at no puede ser anterior a started_at")
            if emotion is None:
                raise ValueError("recognized_at requiere la expresión registrada")
        if state is SessionState.RECOGNIZED and self.recognized_at is None:
            raise ValueError("una sesión reconocida requiere recognized_at")

        if state is SessionState.COMPLETED:
            if emotion is None or exercise_result is None:
                raise ValueError(
                    "una sesión completada requiere emoción y resultado de la actividad"
                )
            # Omitir o cancelar la actividad conserva la expresión registrada;
            # solo una actividad completada exige actividad y duración.
            if exercise_result == ActivityOutcome.COMPLETED.value and (
                activity_id is None or self.exercise_duration_seconds is None
            ):
                raise ValueError(
                    "una sesión con actividad completada requiere actividad y duración"
                )

        object.__setattr__(self, "id", session_id)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "initial_emotion", emotion)
        object.__setattr__(self, "activity_id", activity_id)
        object.__setattr__(self, "exercise_result", exercise_result)
        object.__setattr__(self, "student_id", student_id)
        object.__setattr__(self, "emotion_model_id", model_id)
        object.__setattr__(self, "emotion_model_version", model_version)

    def _validate_progress(self) -> None:
        values = (self.exercise_steps_completed, self.exercise_steps_total, self.exercise_repetitions)
        if all(value is None for value in values):
            return
        if any(value is None for value in values):
            raise ValueError("el avance de la actividad requiere pasos completados, total y repeticiones")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise TypeError("el avance de la actividad debe expresarse con enteros")
        completed, total, repetitions = values
        if repetitions < 1 or total < repetitions or total % repetitions:
            raise ValueError("el total de pasos debe ser un múltiplo positivo de las repeticiones")
        if not 0 <= completed <= total:
            raise ValueError("los pasos completados deben estar entre 0 y el total")

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
