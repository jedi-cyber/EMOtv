from __future__ import annotations

import time
from collections.abc import Callable

from emotv.config import ARMS_UP_HOLD_SECONDS, POSE_DROPOUT_TOLERANCE_SECONDS
from emotv.domain.exercise_status import ExerciseState, ExerciseStatus


class ExerciseService:
    """Controla el tiempo de una postura mediante una maquina de estados.

    El tiempo solo se acumula entre frames consecutivos con la postura
    correcta. Reglas cuando la postura se pierde:

    - ``update(False)``: los landmarks se ven y la postura es incorrecta (u
      otra postura): el tiempo del paso se reinicia a cero.
    - ``pause()``: el frame no trae landmarks utilizables (parpadeo de la
      detección). El tiempo se congela sin perderse; si el hueco desde el
      último frame correcto supera ``dropout_tolerance_seconds``, se reinicia.
    """

    def __init__(
        self,
        duration_seconds: float = ARMS_UP_HOLD_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        dropout_tolerance_seconds: float = POSE_DROPOUT_TOLERANCE_SECONDS,
    ) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds debe ser mayor que cero")
        if dropout_tolerance_seconds < 0:
            raise ValueError("dropout_tolerance_seconds no puede ser negativa")

        self.duration_seconds = float(duration_seconds)
        self.dropout_tolerance_seconds = float(dropout_tolerance_seconds)
        self._clock = clock
        self._held = 0.0
        self._last_valid_at: float | None = None
        # Falso tras una pausa: el hueco no cuenta como tiempo sostenido.
        self._counting = False
        self._status = ExerciseStatus(
            state=ExerciseState.INCORRECT,
            progress=0.0,
            elapsed_seconds=0.0,
        )

    @property
    def status(self) -> ExerciseStatus:
        return self._status

    def update(self, posture_correct: bool) -> ExerciseStatus:
        if self._status.completed:
            return self._status

        if not posture_correct:
            return self.reset()

        now = self._clock()
        if self._counting and self._last_valid_at is not None:
            self._held += max(0.0, now - self._last_valid_at)
        self._last_valid_at = now
        self._counting = True

        progress = min(self._held / self.duration_seconds, 1.0)
        self._status = ExerciseStatus(
            state=ExerciseState.COMPLETED if progress >= 1.0 else ExerciseState.HOLDING,
            progress=progress,
            elapsed_seconds=min(self._held, self.duration_seconds),
        )
        return self._status

    def pause(self) -> ExerciseStatus:
        """Frame sin landmarks utilizables: congela el tiempo o lo reinicia."""

        if self._status.completed:
            return self._status
        self._counting = False
        if self._last_valid_at is None:
            return self._status
        if self._clock() - self._last_valid_at > self.dropout_tolerance_seconds:
            return self.reset()
        return self._status

    def reset(self) -> ExerciseStatus:
        self._held = 0.0
        self._last_valid_at = None
        self._counting = False
        self._status = ExerciseStatus(
            state=ExerciseState.INCORRECT,
            progress=0.0,
            elapsed_seconds=0.0,
        )
        return self._status

    def start_step(self, duration_seconds: float) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds debe ser mayor que cero")
        self.duration_seconds = float(duration_seconds)
        self.reset()
