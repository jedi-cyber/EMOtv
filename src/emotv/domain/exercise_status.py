from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExerciseState(str, Enum):
    INCORRECT = "incorrect"
    HOLDING = "holding"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ExerciseStatus:
    state: ExerciseState
    progress: float
    elapsed_seconds: float

    @property
    def completed(self) -> bool:
        return self.state is ExerciseState.COMPLETED
