from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from emotv.domain.activity import Activity
from emotv.domain.exercise_status import ExerciseStatus
from emotv.domain.posture_result import PostureResult
from emotv.domain.stabilized_emotion import StabilizedEmotion


class EmotionalActivityState(str, Enum):
    ANALYZING_EMOTION = "analyzing_emotion"
    ACTIVITY_SELECTED = "activity_selected"
    WAITING_FOR_POSTURE = "waiting_for_posture"
    PERFORMING_EXERCISE = "performing_exercise"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class EmotionalActivityStatus:
    state: EmotionalActivityState
    message: str
    emotion: StabilizedEmotion | None = None
    activity: Activity | None = None
    posture: PostureResult | None = None
    exercise: ExerciseStatus | None = None

    @property
    def completed(self) -> bool:
        return self.state is EmotionalActivityState.COMPLETED
