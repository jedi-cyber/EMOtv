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
    ) -> None:
        self.activity = activity
        self.emotion_analyzer = emotion_analyzer
        self.pose_service = pose_service
        self.emotion_stabilizer = emotion_stabilizer or EmotionStabilizer()
        self.exercise_service = exercise_service or ExerciseService(
            activity.duration_seconds
        )
        self.emotion: StabilizedEmotion | None = None
        self._closed = False

    @property
    def last_pose_result(self) -> PoseResult | None:
        return self.pose_service.last_pose_result

    def process_frame(self, frame: np.ndarray) -> EmotionalActivityStatus:
        if self._closed:
            raise RuntimeError("El procesador de actividad está cerrado")
        if self.exercise_service.status.completed:
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
            self.activity.required_posture.value,
        )
        correct = posture is not None and posture.detected
        exercise = self.exercise_service.update(correct)
        if exercise.completed:
            state = EmotionalActivityState.COMPLETED
            message = "Actividad completada"
        elif correct:
            state = EmotionalActivityState.PERFORMING_EXERCISE
            message = "Mantén la postura"
        else:
            state = EmotionalActivityState.WAITING_FOR_POSTURE
            message = posture.message if posture is not None else "Coloca el cuerpo completo dentro de la cámara"
        return EmotionalActivityStatus(
            state=state,
            message=message,
            emotion=self.emotion,
            activity=self.activity,
            posture=posture,
            exercise=exercise,
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
            exercise=self.exercise_service.status,
        )
