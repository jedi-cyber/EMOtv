from __future__ import annotations

import unittest

from emotv.domain import PoseLandmark
from emotv.infrastructure.vision.movement_analysis import calculate_angle


class AngleCalculatorTests(unittest.TestCase):
    def test_calculates_straight_angle(self) -> None:
        angle = calculate_angle(
            PoseLandmark(0.0, 0.0),
            PoseLandmark(1.0, 0.0),
            PoseLandmark(2.0, 0.0),
        )

        self.assertAlmostEqual(angle, 180.0)

    def test_calculates_right_angle(self) -> None:
        angle = calculate_angle(
            PoseLandmark(1.0, 0.0),
            PoseLandmark(0.0, 0.0),
            PoseLandmark(0.0, 1.0),
        )

        self.assertAlmostEqual(angle, 90.0)

    def test_calculates_closed_angle(self) -> None:
        angle = calculate_angle(
            PoseLandmark(1.0, 0.0),
            PoseLandmark(0.0, 0.0),
            PoseLandmark(2.0, 0.0),
        )

        self.assertAlmostEqual(angle, 0.0)

    def test_coincident_vertex_returns_zero(self) -> None:
        angle = calculate_angle(
            PoseLandmark(0.0, 0.0),
            PoseLandmark(0.0, 0.0),
            PoseLandmark(1.0, 0.0),
        )

        self.assertEqual(angle, 0.0)


if __name__ == "__main__":
    unittest.main()
