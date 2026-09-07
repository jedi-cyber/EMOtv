from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import numpy as np

from emotv.application.activity_recommendation_service import (
    ActivityRecommendationService,
)
from emotv.application.emotion_stabilizer import EmotionStabilizer
from emotv.application.exercise_service import ExerciseService
from emotv.application.pose_service import PoseService
from emotv.domain.cropped_face import CroppedFace
from emotv.domain.emotional_activity_status import (
    EmotionalActivityState,
    EmotionalActivityStatus,
)
from emotv.domain.posture_id import PostureId
from emotv.domain.posture_result import PostureResult
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import (
    EmotionClassifier,
)


class EmotionClassifierProtocol(Protocol):
    def predict(self, cropped_face: CroppedFace) -> tuple[str, float]: ...


class PoseServiceProtocol(Protocol):
    def validate(
        self,
        frame: np.ndarray,
        posture_id: PostureId | str,
    ) -> PostureResult | None: ...


ExerciseServiceFactory = Callable[[float], ExerciseService]


class EmotionalActivityService:
    """Coordina el flujo local de emoción, actividad, postura y ejercicio."""

    def __init__(
        self,
        emotion_classifier: EmotionClassifierProtocol | None = None,
        emotion_stabilizer: EmotionStabilizer | None = None,
        recommendation_service: ActivityRecommendationService | None = None,
        pose_service: PoseServiceProtocol | None = None,
        exercise_factory: ExerciseServiceFactory = ExerciseService,
    ) -> None:
        self.emotion_classifier = emotion_classifier or EmotionClassifier()
        self.emotion_stabilizer = emotion_stabilizer or EmotionStabilizer()
        self.recommendation_service = (
            recommendation_service or ActivityRecommendationService()
        )
        self.pose_service = pose_service or PoseService()
        self.exercise_factory = exercise_factory
        self._exercise_service: ExerciseService | None = None
        self._status = EmotionalActivityStatus(
            state=EmotionalActivityState.ANALYZING_EMOTION,
            message="Analizando expresión emocional",
        )

    @property
    def status(self) -> EmotionalActivityStatus:
        return self._status

    def observe_face(self, cropped_face: CroppedFace) -> EmotionalActivityStatus:
        """Clasifica un rostro y agrega la predicción al estabilizador."""

        emotion, confidence = self.emotion_classifier.predict(cropped_face)
        return self.observe_emotion(emotion, confidence)

    def observe_emotion(
        self,
        emotion: str,
        confidence: float,
    ) -> EmotionalActivityStatus:
        """Agrega una predicción ya calculada al flujo emocional."""

        if self._status.state is not EmotionalActivityState.ANALYZING_EMOTION:
            raise RuntimeError("El flujo ya terminó la etapa de análisis emocional")

        stabilized = self.emotion_stabilizer.update(emotion, confidence)
        if stabilized is None:
            self._status = EmotionalActivityStatus(
                state=EmotionalActivityState.ANALYZING_EMOTION,
                message="Reuniendo predicciones emocionales",
            )
            return self._status

        activity = self.recommendation_service.recommend(stabilized.emotion)
        if activity is None:
            self._status = EmotionalActivityStatus(
                state=EmotionalActivityState.ANALYZING_EMOTION,
                message="La emoción estable no tiene una actividad configurada",
                emotion=stabilized,
            )
            return self._status

        self._exercise_service = self.exercise_factory(activity.duration_seconds)
        self._status = EmotionalActivityStatus(
            state=EmotionalActivityState.ACTIVITY_SELECTED,
            message=activity.description,
            emotion=stabilized,
            activity=activity,
            exercise=self._exercise_service.status,
        )
        return self._status

    def begin_activity(self) -> EmotionalActivityStatus:
        """Confirma la actividad seleccionada y habilita el análisis corporal."""

        if self._status.state is not EmotionalActivityState.ACTIVITY_SELECTED:
            raise RuntimeError("No hay una actividad seleccionada para iniciar")
        assert self._status.activity is not None
        assert self._exercise_service is not None

        self._status = EmotionalActivityStatus(
            state=EmotionalActivityState.WAITING_FOR_POSTURE,
            message="Esperando la postura requerida",
            emotion=self._status.emotion,
            activity=self._status.activity,
            exercise=self._exercise_service.status,
        )
        return self._status

    def process_pose_frame(self, frame: np.ndarray) -> EmotionalActivityStatus:
        """Detecta la postura objetivo y actualiza el ejercicio activo."""

        if self._status.state is EmotionalActivityState.COMPLETED:
            return self._status
        if self._status.state not in {
            EmotionalActivityState.WAITING_FOR_POSTURE,
            EmotionalActivityState.PERFORMING_EXERCISE,
        }:
            raise RuntimeError("El flujo aún no está preparado para analizar postura")

        activity = self._status.activity
        assert activity is not None
        assert self._exercise_service is not None
        posture = self.pose_service.validate(frame, activity.required_posture)
        posture_correct = posture is not None and posture.detected
        exercise = self._exercise_service.update(posture_correct)

        if exercise.completed:
            state = EmotionalActivityState.COMPLETED
            message = "Actividad completada"
        elif posture_correct:
            state = EmotionalActivityState.PERFORMING_EXERCISE
            message = "Mantén la postura"
        else:
            state = EmotionalActivityState.WAITING_FOR_POSTURE
            message = "Esperando la postura requerida"

        self._status = EmotionalActivityStatus(
            state=state,
            message=message,
            emotion=self._status.emotion,
            activity=activity,
            posture=posture,
            exercise=exercise,
        )
        return self._status

    def reset(self) -> EmotionalActivityStatus:
        self.emotion_stabilizer.reset()
        self._exercise_service = None
        self._status = EmotionalActivityStatus(
            state=EmotionalActivityState.ANALYZING_EMOTION,
            message="Analizando expresión emocional",
        )
        return self._status

    def close(self) -> None:
        close = getattr(self.pose_service, "close", None)
        if callable(close):
            close()
