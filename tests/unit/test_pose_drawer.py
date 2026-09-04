from __future__ import annotations

import unittest

import numpy as np

from emotv.domain.pose_landmarks import PoseLandmark, PoseLandmarks
from emotv.interfaces.ui.pose_drawer import PoseDrawer


def make_pose(visibility: float = 1.0) -> PoseLandmarks:
    def point(x: float, y: float) -> PoseLandmark:
        return PoseLandmark(x=x, y=y, visibility=visibility)

    return PoseLandmarks(
        nose=point(0.5, 0.1),
        left_shoulder=point(0.35, 0.25),
        right_shoulder=point(0.65, 0.25),
        left_elbow=point(0.25, 0.45),
        right_elbow=point(0.75, 0.45),
        left_wrist=point(0.2, 0.65),
        right_wrist=point(0.8, 0.65),
        left_hip=point(0.4, 0.55),
        right_hip=point(0.6, 0.55),
        left_knee=point(0.4, 0.75),
        right_knee=point(0.6, 0.75),
        left_ankle=point(0.4, 0.95),
        right_ankle=point(0.6, 0.95),
    )


class PoseDrawerTests(unittest.TestCase):
    def test_draws_without_modifying_original_frame(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        result = PoseDrawer().draw(frame, make_pose())

        self.assertEqual(int(frame.sum()), 0)
        self.assertGreater(int(result.sum()), 0)
        self.assertIsNot(result, frame)

    def test_ignores_landmarks_below_visibility_threshold(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        result = PoseDrawer(min_visibility=0.5).draw(
            frame,
            make_pose(visibility=0.1),
        )

        np.testing.assert_array_equal(result, frame)

    def test_clamps_landmarks_outside_the_frame(self) -> None:
        drawer = PoseDrawer()

        self.assertEqual(drawer._to_pixel(PoseLandmark(-1, 2), 100, 80), (0, 79))


if __name__ == "__main__":
    unittest.main()
