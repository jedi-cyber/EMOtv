from __future__ import annotations

import time
from collections.abc import Callable

from emotv.config import ARMS_UP_HOLD_SECONDS
from emotv.domain.exercise_status import ExerciseState, ExerciseStatus


class ExerciseService:
    """Controla el tiempo de una postura mediante una maquina de estados."""

    def __init__(
        self,
        duration_seconds: float = ARMS_UP_HOLD_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds debe ser mayor que cero")

        self.duration_seconds = float(duration_seconds)
        self._clock = clock
        self._started_at: float | None = None
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
        if self._started_at is None:
            self._started_at = now

        elapsed = max(0.0, now - self._started_at)
        progress = min(elapsed / self.duration_seconds, 1.0)
        state = (
            ExerciseState.COMPLETED
            if progress >= 1.0
            else ExerciseState.HOLDING
        )
        self._status = ExerciseStatus(
            state=state,
            progress=progress,
            elapsed_seconds=min(elapsed, self.duration_seconds),
        )
        return self._status

    def reset(self) -> ExerciseStatus:
        self._started_at = None
        self._status = ExerciseStatus(
            state=ExerciseState.INCORRECT,
            progress=0.0,
            elapsed_seconds=0.0,
        )
        return self._status
