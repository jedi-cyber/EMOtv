from __future__ import annotations

import unittest

import numpy as np

from emotv.application import (
    ActivityRecommendationService,
    EmotionStabilizer,
    EmotionalActivityService,
)
from emotv.application.exercise_service import ExerciseService
from emotv.domain import (
    CroppedFace,
    EmotionalActivityState,
    PostureId,
    PostureResult,
)
from scripts.run_emotional_exercise_test import build_final_result


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class FakeEmotionClassifier:
    def __init__(self, result: tuple[str, float] = ("sadness", 0.9)) -> None:
        self.result = result

    def predict(self, cropped_face: CroppedFace) -> tuple[str, float]:
        return self.result


class FakePoseService:
    def __init__(self) -> None:
        self.result: PostureResult | None = None
        self.requested_postures: list[PostureId | str] = []
        self.closed = False

    def validate(
        self,
        frame: np.ndarray,
        posture_id: PostureId | str,
    ) -> PostureResult | None:
        self.requested_postures.append(posture_id)
        return self.result

    def close(self) -> None:
        self.closed = True


class EmotionalActivityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.pose_service = FakePoseService()
        self.service = EmotionalActivityService(
            emotion_classifier=FakeEmotionClassifier(),
            emotion_stabilizer=EmotionStabilizer(
                window_size=1,
                min_samples=1,
            ),
            recommendation_service=ActivityRecommendationService(),
            pose_service=self.pose_service,
            exercise_factory=lambda duration: ExerciseService(duration, self.clock),
        )
        self.frame = np.zeros((10, 10, 3), dtype=np.uint8)

    def select_activity(self) -> None:
        status = self.service.observe_emotion("sadness", 0.9)
        self.assertEqual(status.state, EmotionalActivityState.ACTIVITY_SELECTED)

    def test_starts_analyzing_emotion(self) -> None:
        self.assertEqual(
            self.service.status.state,
            EmotionalActivityState.ANALYZING_EMOTION,
        )

    def test_observe_face_uses_classifier_and_selects_activity(self) -> None:
        face = CroppedFace(
            image=np.zeros((64, 64), dtype=np.uint8),
            bbox=(0, 0, 64, 64),
            confidence=0.9,
        )

        status = self.service.observe_face(face)

        self.assertEqual(status.state, EmotionalActivityState.ACTIVITY_SELECTED)
        assert status.emotion is not None
        assert status.activity is not None
        self.assertEqual(status.emotion.emotion, "sadness")
        self.assertEqual(status.activity.id, "arms_up_5s")

    def test_waits_until_emotion_is_stable(self) -> None:
        service = EmotionalActivityService(
            emotion_classifier=FakeEmotionClassifier(),
            emotion_stabilizer=EmotionStabilizer(window_size=3, min_samples=3),
            recommendation_service=ActivityRecommendationService(),
            pose_service=self.pose_service,
        )

        status = service.observe_emotion("sadness", 0.9)

        self.assertEqual(status.state, EmotionalActivityState.ANALYZING_EMOTION)
        self.assertIsNone(status.activity)

    def test_emotion_without_recommendation_continues_analysis(self) -> None:
        status = self.service.observe_emotion("neutral", 0.9)

        self.assertEqual(status.state, EmotionalActivityState.ANALYZING_EMOTION)
        self.assertIsNotNone(status.emotion)
        self.assertIsNone(status.activity)

    def test_begin_activity_transitions_to_waiting_for_posture(self) -> None:
        self.select_activity()

        status = self.service.begin_activity()

        self.assertEqual(status.state, EmotionalActivityState.WAITING_FOR_POSTURE)

    def test_incorrect_posture_remains_waiting(self) -> None:
        self.select_activity()
        self.service.begin_activity()
        self.pose_service.result = PostureResult(PostureId.ARMS_UP, detected=False)

        status = self.service.process_pose_frame(self.frame)

        self.assertEqual(status.state, EmotionalActivityState.WAITING_FOR_POSTURE)
        assert status.exercise is not None
        self.assertEqual(status.exercise.progress, 0.0)

    def test_correct_posture_performs_and_completes_exercise(self) -> None:
        self.select_activity()
        self.service.begin_activity()
        self.pose_service.result = PostureResult(PostureId.ARMS_UP, detected=True)

        holding = self.service.process_pose_frame(self.frame)
        self.clock.value = 5.0
        completed = self.service.process_pose_frame(self.frame)

        self.assertEqual(holding.state, EmotionalActivityState.PERFORMING_EXERCISE)
        self.assertEqual(completed.state, EmotionalActivityState.COMPLETED)
        self.assertTrue(completed.completed)
        assert completed.exercise is not None
        self.assertEqual(completed.exercise.progress, 1.0)
        self.assertEqual(self.pose_service.requested_postures, [
            PostureId.ARMS_UP,
            PostureId.ARMS_UP,
        ])
        self.assertEqual(
            build_final_result(completed),
            {
                "initial_emotion": "sadness",
                "emotion_confidence": 0.9,
                "activity": "arms_up_5s",
                "exercise_result": "completed",
                "elapsed_seconds": 5.0,
            },
        )

    def test_final_result_rejects_incomplete_flow(self) -> None:
        with self.assertRaises(ValueError):
            build_final_result(self.service.status)

    def test_completed_state_is_terminal(self) -> None:
        self.select_activity()
        self.service.begin_activity()
        self.pose_service.result = PostureResult(PostureId.ARMS_UP, detected=True)
        self.service.process_pose_frame(self.frame)
        self.clock.value = 5.0
        completed = self.service.process_pose_frame(self.frame)

        self.assertIs(self.service.process_pose_frame(self.frame), completed)

    def test_reset_returns_to_emotion_analysis(self) -> None:
        self.select_activity()

        status = self.service.reset()

        self.assertEqual(status.state, EmotionalActivityState.ANALYZING_EMOTION)
        self.assertIsNone(status.activity)

    def test_rejects_invalid_transition(self) -> None:
        with self.assertRaises(RuntimeError):
            self.service.begin_activity()
        with self.assertRaises(RuntimeError):
            self.service.process_pose_frame(self.frame)

    def test_close_releases_pose_service(self) -> None:
        self.service.close()

        self.assertTrue(self.pose_service.closed)


if __name__ == "__main__":
    unittest.main()
