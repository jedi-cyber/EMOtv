from __future__ import annotations

from typing import Protocol

import numpy as np

from emotv.application.emotion_stabilizer import EmotionStabilizer
from emotv.application.exercise_service import ExerciseService
from emotv.domain.activity import Activity, ActivityStep
from emotv.domain.emotional_activity_status import (
    EmotionalActivityState,
    EmotionalActivityStatus,
)
from emotv.domain.pose_result import PoseResult
from emotv.domain.posture_result import PostureResult
from emotv.domain.stabilized_emotion import StabilizedEmotion
from emotv.domain.exercise_status import ExerciseState, ExerciseStatus

NO_BODY_MESSAGE = "No se te ve en la cámara: aléjate un poco y céntrate en la imagen"


class EmotionFrameAnalyzerProtocol(Protocol):
    def analyze(self, frame: np.ndarray) -> tuple[str, float] | None: ...


class PoseServiceProtocol(Protocol):
    @property
    def last_pose_result(self) -> PoseResult | None: ...

    def validate(self, frame: np.ndarray, posture_id: str) -> PostureResult | None: ...

    def close(self) -> None: ...


class BrowserActivityService:
    """Procesa frames remotos durante una actividad elegida por el estudiante.

    La secuencia completa son ``len(steps) × repetitions`` pasos. Solo se
    evalúa la postura del paso actual y solo esa hace avanzar su tiempo; las
    reglas de pausa y reinicio están en :class:`ExerciseService`.
    """

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
        self.exercise_service.start_step(activity.steps[0].duration_seconds)
        self.emotion: StabilizedEmotion | None = initial_emotion
        self._closed = False
        # Pasos completados en toda la secuencia.
        self._step_index = 0
        self._elapsed_total = 0.0

    @property
    def steps_per_repetition(self) -> int:
        return len(self.activity.steps)

    @property
    def step_count(self) -> int:
        return self.steps_per_repetition * self.activity.repetitions

    @property
    def finished(self) -> bool:
        return self._step_index >= self.step_count

    @property
    def current_step(self) -> ActivityStep:
        index = min(self._step_index, self.step_count - 1)
        return self.activity.steps[index % self.steps_per_repetition]

    @property
    def last_pose_result(self) -> PoseResult | None:
        return self.pose_service.last_pose_result

    def process_frame(self, frame: np.ndarray) -> EmotionalActivityStatus:
        if self._closed:
            raise RuntimeError("El procesador de actividad está cerrado")
        if self.finished:
            return self._status(EmotionalActivityState.COMPLETED, "Actividad completada")

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
                "Expresión registrada. Adopta la postura indicada",
            )

        step = self.current_step
        posture = self.pose_service.validate(frame, step.posture.value)
        if posture is None or not posture.landmarks_visible:
            # Parpadeo de la detección o cuerpo fuera de cuadro: el tiempo se
            # congela y solo se reinicia si el hueco supera la tolerancia.
            exercise = self.exercise_service.pause()
            message = posture.message if posture is not None else NO_BODY_MESSAGE
        elif posture.posture_id is not step.posture:
            # Un resultado de otra postura nunca cuenta, aunque sea válido.
            exercise = self.exercise_service.update(False)
            message = "Adopta la postura indicada: " + step.instruction
        else:
            exercise = self.exercise_service.update(posture.detected)
            message = "Mantén la postura" if posture.detected else posture.message

        if exercise.completed:
            self._elapsed_total += exercise.elapsed_seconds
            self._step_index += 1
            if self.finished:
                return self._status(
                    EmotionalActivityState.COMPLETED, "Actividad completada", posture,
                )
            next_step = self.current_step
            self.exercise_service.start_step(next_step.duration_seconds)
            return self._status(
                EmotionalActivityState.WAITING_FOR_POSTURE,
                "Siguiente postura: " + next_step.instruction,
                posture,
            )
        state = (
            EmotionalActivityState.PERFORMING_EXERCISE
            if exercise.state is ExerciseState.HOLDING
            else EmotionalActivityState.WAITING_FOR_POSTURE
        )
        return self._status(state, message, posture)

    def close(self) -> None:
        if not self._closed:
            self.pose_service.close()
            self._closed = True

    def _status(
        self,
        state: EmotionalActivityState,
        message: str,
        posture: PostureResult | None = None,
    ) -> EmotionalActivityStatus:
        finished = self.finished
        step = self.current_step
        current = self.exercise_service.status
        step_elapsed = step.duration_seconds if finished else current.elapsed_seconds
        index = min(self._step_index, self.step_count - 1)
        return EmotionalActivityStatus(
            state=state,
            message=message,
            emotion=self.emotion,
            activity=self.activity,
            posture=posture,
            exercise=ExerciseStatus(
                state=ExerciseState.COMPLETED if finished else current.state,
                # Progreso global: pasos completados / (pasos × repeticiones).
                progress=self._step_index / self.step_count,
                elapsed_seconds=self._elapsed_total + (0.0 if finished else step_elapsed),
            ),
            step_index=index,
            step_count=self.step_count,
            repetition_index=index // self.steps_per_repetition,
            repetition_count=self.activity.repetitions,
            steps_completed=self._step_index,
            step_elapsed_seconds=step_elapsed,
            step_duration_seconds=step.duration_seconds,
        )
