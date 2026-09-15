from __future__ import annotations

import unittest

import numpy as np

from emotv.application import BrowserActivityService, EmotionStabilizer
from emotv.application.exercise_service import ExerciseService
from emotv.domain import Activity, EmotionalActivityState, PoseResult, PostureId, PostureResult


class Analyzer:
    def analyze(self, frame: np.ndarray) -> tuple[str, float] | None:
        return "neutral", 0.9


class Pose:
    def __init__(self) -> None:
        self.correct = False
        self.closed = False

    @property
    def last_pose_result(self) -> PoseResult | None:
        return None

    def validate(self, frame: np.ndarray, posture_id: str) -> PostureResult:
        return PostureResult(posture_id, self.correct, 1.0 if self.correct else 0.0)

    def close(self) -> None:
        self.closed = True


class Clock:
    value = 0.0

    def __call__(self) -> float:
        return self.value


class BrowserActivityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pose = Pose()
        self.clock = Clock()
        activity = Activity("activity", "Actividad", "Instrucción", PostureId.ARMS_UP, 2.0)
        self.service = BrowserActivityService(
            activity,
            Analyzer(),
            self.pose,
            EmotionStabilizer(window_size=1, min_samples=1),
            ExerciseService(2.0, self.clock),
        )
        self.frame = np.zeros((10, 10, 3), dtype=np.uint8)

    def test_transitions_from_emotion_to_posture_and_completion(self) -> None:
        emotion = self.service.process_frame(self.frame)
        incorrect = self.service.process_frame(self.frame)
        self.pose.correct = True
        holding = self.service.process_frame(self.frame)
        self.clock.value = 2.0
        completed = self.service.process_frame(self.frame)

        self.assertIs(emotion.state, EmotionalActivityState.WAITING_FOR_POSTURE)
        self.assertIs(incorrect.state, EmotionalActivityState.WAITING_FOR_POSTURE)
        self.assertIs(holding.state, EmotionalActivityState.PERFORMING_EXERCISE)
        self.assertIs(completed.state, EmotionalActivityState.COMPLETED)
        self.assertEqual(completed.exercise.progress, 1.0)

    def test_close_releases_pose_detector(self) -> None:
        self.service.close()

        self.assertTrue(self.pose.closed)
        with self.assertRaises(RuntimeError):
            self.service.process_frame(self.frame)


if __name__ == "__main__":
    unittest.main()
