from __future__ import annotations

import unittest

import numpy as np

from emotv.application.exercise_service import ExerciseService
from emotv.domain.exercise_status import ExerciseState, ExerciseStatus
from scripts.poses.run_exercise_test import draw_progress_bar, state_presentation


class FakeClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class ExerciseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock(10.0)
        self.service = ExerciseService(duration_seconds=5.0, clock=self.clock)

    def test_starts_as_incorrect_with_zero_progress(self) -> None:
        status = self.service.status

        self.assertEqual(status.state, ExerciseState.INCORRECT)
        self.assertEqual(status.progress, 0.0)
        self.assertEqual(status.elapsed_seconds, 0.0)

    def test_correct_posture_transitions_to_holding(self) -> None:
        status = self.service.update(True)

        self.assertEqual(status.state, ExerciseState.HOLDING)
        self.assertEqual(status.progress, 0.0)

    def test_holding_reports_normalized_progress(self) -> None:
        self.service.update(True)
        self.clock.value = 12.5

        status = self.service.update(True)

        self.assertEqual(status.state, ExerciseState.HOLDING)
        self.assertAlmostEqual(status.progress, 0.5)
        self.assertAlmostEqual(status.elapsed_seconds, 2.5)

    def test_incorrect_posture_resets_holding(self) -> None:
        self.service.update(True)
        self.clock.value = 12.5
        self.service.update(True)

        status = self.service.update(False)

        self.assertEqual(status.state, ExerciseState.INCORRECT)
        self.assertEqual(status.progress, 0.0)

    def test_reaching_duration_completes_exercise(self) -> None:
        self.service.update(True)
        self.clock.value = 15.0

        status = self.service.update(True)

        self.assertEqual(status.state, ExerciseState.COMPLETED)
        self.assertEqual(status.progress, 1.0)
        self.assertTrue(status.completed)

    def test_completed_state_is_terminal_until_reset(self) -> None:
        self.service.update(True)
        self.clock.value = 20.0
        completed = self.service.update(True)

        self.assertIs(self.service.update(False), completed)
        self.assertEqual(self.service.status.state, ExerciseState.COMPLETED)

        reset = self.service.reset()
        self.assertEqual(reset.state, ExerciseState.INCORRECT)

    def test_rejects_non_positive_duration(self) -> None:
        with self.assertRaises(ValueError):
            ExerciseService(duration_seconds=0.0)

    def test_progress_bar_clamps_values_to_zero_and_one(self) -> None:
        negative = np.zeros((200, 400, 3), dtype=np.uint8)
        zero = negative.copy()
        over_one = negative.copy()
        one = negative.copy()

        draw_progress_bar(negative, -0.5, (0, 255, 0))
        draw_progress_bar(zero, 0.0, (0, 255, 0))
        draw_progress_bar(over_one, 1.5, (0, 255, 0))
        draw_progress_bar(one, 1.0, (0, 255, 0))

        np.testing.assert_array_equal(negative, zero)
        np.testing.assert_array_equal(over_one, one)

    def test_completed_state_has_completion_message(self) -> None:
        message, _ = state_presentation(
            ExerciseStatus(ExerciseState.COMPLETED, 1.0, 5.0),
        )

        self.assertIn("COMPLETADO", message)


if __name__ == "__main__":
    unittest.main()
