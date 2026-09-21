from __future__ import annotations

from typing import Protocol

import numpy as np

from emotv.application.emotion_stabilizer import EmotionStabilizer
from emotv.application.exercise_service import ExerciseService
from emotv.domain.activity import Activity
from emotv.domain.emotional_activity_status import (
    EmotionalActivityState,
    EmotionalActivityStatus,
)
from emotv.domain.pose_result import PoseResult
from emotv.domain.posture_result import PostureResult
from emotv.domain.stabilized_emotion import StabilizedEmotion
from emotv.domain.exercise_status import ExerciseState, ExerciseStatus


class EmotionFrameAnalyzerProtocol(Protocol):
    def analyze(self, frame: np.ndarray) -> tuple[str, float] | None: ...


class PoseServiceProtocol(Protocol):
    @property
    def last_pose_result(self) -> PoseResult | None: ...

    def validate(self, frame: np.ndarray, posture_id: str) -> PostureResult | None: ...

    def close(self) -> None: ...


class BrowserActivityService:
    """Procesa frames remotos durante una actividad elegida por el estudiante."""

    def __init__(
        self,
        activity: Activity,
        emotion_analyzer: EmotionFrameAnalyzerProtocol,
        pose_service: PoseServiceProtocol,
        emotion_stabilizer: EmotionStabilizer | None = None,
        exercise_service: ExerciseService | None = None,
        initial_emotion: StabilizedEmotion | None = None,
    ) -> None:
        self.activity = activity
        self.emotion_analyzer = emotion_analyzer
        self.pose_service = pose_service
        self.emotion_stabilizer = emotion_stabilizer or EmotionStabilizer()
        self.exercise_service = exercise_service or ExerciseService(
            activity.steps[0].duration_seconds
        )
        self.emotion: StabilizedEmotion | None = initial_emotion
        self._closed = False
        self._step_index = 0
        self._elapsed_total = 0.0

    @property
    def step_count(self) -> int:
        return len(self.activity.steps) * self.activity.repetitions

    @property
    def current_step(self):
        return self.activity.steps[min(self._step_index, self.step_count - 1) % len(self.activity.steps)]

    @property
    def last_pose_result(self) -> PoseResult | None:
        return self.pose_service.last_pose_result

    def process_frame(self, frame: np.ndarray) -> EmotionalActivityStatus:
        if self._closed:
            raise RuntimeError("El procesador de actividad está cerrado")
        if self._step_index >= self.step_count:
            return self._status(
                EmotionalActivityState.COMPLETED,
                "Actividad completada",
            )

        if self.emotion is None:
            prediction = self.emotion_analyzer.analyze(frame)
            if prediction is None:
                return self._status(
                    EmotionalActivityState.ANALYZING_EMOTION,
                    "Ubica el rostro dentro de la cámara",
                )
            self.emotion = self.emotion_stabilizer.update(*prediction)
            if self.emotion is None:
                return self._status(
                    EmotionalActivityState.ANALYZING_EMOTION,
                    "Analizando la expresión facial",
                )
            return self._status(
                EmotionalActivityState.WAITING_FOR_POSTURE,
                "Emoción estabilizada. Adopta la postura indicada",
            )

        posture = self.pose_service.validate(
            frame,
            self.current_step.posture.value,
        )
        correct = posture is not None and posture.detected
        exercise = self.exercise_service.update(correct)
        if exercise.completed:
            self._elapsed_total += self.current_step.duration_seconds
            self._step_index += 1
            if self._step_index >= self.step_count:
                state = EmotionalActivityState.COMPLETED
                message = "Actividad completada"
            else:
                state = EmotionalActivityState.WAITING_FOR_POSTURE
                message = "Siguiente postura: " + self.current_step.instruction
                self.exercise_service.start_step(self.current_step.duration_seconds)
                exercise = self.exercise_service.status
        elif correct:
            state = EmotionalActivityState.PERFORMING_EXERCISE
            message = "Mantén la postura"
        else:
            state = EmotionalActivityState.WAITING_FOR_POSTURE
            message = posture.message if posture is not None else "Coloca el cuerpo completo dentro de la cámara"
        overall = ExerciseStatus(
            state=ExerciseState.COMPLETED if state is EmotionalActivityState.COMPLETED else exercise.state,
            progress=min((self._step_index + (0 if state is EmotionalActivityState.COMPLETED else exercise.progress)) / self.step_count, 1.0),
            elapsed_seconds=self._elapsed_total + (0 if state is EmotionalActivityState.COMPLETED else exercise.elapsed_seconds),
        )
        return EmotionalActivityStatus(
            state=state,
            message=message,
            emotion=self.emotion,
            activity=self.activity,
            posture=posture,
            exercise=overall,
            step_index=min(self._step_index, self.step_count - 1),
            step_count=self.step_count,
        )

    def close(self) -> None:
        if not self._closed:
            self.pose_service.close()
            self._closed = True

    def _status(
        self,
        state: EmotionalActivityState,
        message: str,
    ) -> EmotionalActivityStatus:
        return EmotionalActivityStatus(
            state=state,
            message=message,
            emotion=self.emotion,
            activity=self.activity,
            exercise=ExerciseStatus(
                state=ExerciseState.COMPLETED if self._step_index >= self.step_count else self.exercise_service.status.state,
                progress=1.0 if self._step_index >= self.step_count else (self._step_index + self.exercise_service.status.progress) / self.step_count,
                elapsed_seconds=self._elapsed_total + (0 if self._step_index >= self.step_count else self.exercise_service.status.elapsed_seconds),
            ),
            step_index=min(self._step_index, self.step_count - 1),
            step_count=self.step_count,
        )
