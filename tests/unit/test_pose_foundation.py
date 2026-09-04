from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np

from emotv.application.pose_service import PoseService
from emotv.domain.pose_landmarks import PoseLandmark, PoseLandmarks
from emotv.domain.pose_result import PoseResult
from emotv.infrastructure.vision.movement_analysis.posture_validator import (
    ArmsUpThresholds,
    PostureValidator,
)
from scripts.poses.run_posture_test import arm_angles


def make_pose(*, wrists_y: float, shoulders_y: float = 0.4) -> PoseLandmarks:
    point = PoseLandmark(0.5, 0.5)
    elbows_y = (wrists_y + shoulders_y) / 2
    return PoseLandmarks(
        nose=point,
        left_shoulder=PoseLandmark(0.4, shoulders_y),
        right_shoulder=PoseLandmark(0.6, shoulders_y),
        left_elbow=PoseLandmark(0.4, elbows_y),
        right_elbow=PoseLandmark(0.6, elbows_y),
        left_wrist=PoseLandmark(0.4, wrists_y),
        right_wrist=PoseLandmark(0.6, wrists_y),
        left_hip=point,
        right_hip=point,
        left_knee=point,
        right_knee=point,
        left_ankle=point,
        right_ankle=point,
    )


class FakePoseDetector:
    def __init__(self, result: PoseResult) -> None:
        self.result = result

    def detect(self, frame: np.ndarray) -> PoseResult:
        return self.result


class PoseFoundationTests(unittest.TestCase):
    def test_service_returns_none_when_no_pose_is_detected(self) -> None:
        detector = FakePoseDetector(PoseResult(detected=False))
        service = PoseService(detector=detector)

        result = service.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

        self.assertIsNone(result)

    def test_service_detects_both_arms_up(self) -> None:
        pose = make_pose(wrists_y=0.2)
        detector = FakePoseDetector(PoseResult(detected=True, landmarks=pose))
        service = PoseService(detector=detector)

        result = service.analyze(np.zeros((10, 10, 3), dtype=np.uint8))

        self.assertEqual(result, {"pose_detected": True, "arms_up": True})

    def test_validator_rejects_wrists_below_shoulders(self) -> None:
        pose = make_pose(wrists_y=0.6)

        self.assertFalse(PostureValidator().both_arms_up(pose))

    def test_validator_rejects_low_visibility_landmark(self) -> None:
        pose = make_pose(wrists_y=0.2)
        pose = replace(
            pose,
            left_wrist=replace(pose.left_wrist, visibility=0.49),
        )

        self.assertFalse(PostureValidator().both_arms_up(pose))

    def test_validator_rejects_bent_elbow(self) -> None:
        pose = make_pose(wrists_y=0.2)
        pose = replace(
            pose,
            left_elbow=PoseLandmark(0.5, 0.3),
        )

        self.assertFalse(PostureValidator().both_arms_up(pose))

    def test_validator_accepts_configurable_elbow_tolerance(self) -> None:
        pose = make_pose(wrists_y=0.2)
        pose = replace(
            pose,
            left_elbow=PoseLandmark(0.5, 0.3),
        )
        validator = PostureValidator(
            ArmsUpThresholds(elbow_straight_tolerance_degrees=100.0),
        )

        self.assertTrue(validator.both_arms_up(pose))

    def test_validator_applies_configurable_wrist_margin(self) -> None:
        pose = make_pose(wrists_y=0.39)

        self.assertFalse(PostureValidator().both_arms_up(pose))
        self.assertTrue(
            PostureValidator(
                ArmsUpThresholds(wrist_above_shoulder_margin=0.0),
            ).both_arms_up(pose)
        )

    def test_thresholds_reject_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            ArmsUpThresholds(min_visibility=1.1)

    def test_posture_script_reports_straight_elbow_angles(self) -> None:
        left_angle, right_angle = arm_angles(make_pose(wrists_y=0.2))

        self.assertAlmostEqual(left_angle, 180.0)
        self.assertAlmostEqual(right_angle, 180.0)


if __name__ == "__main__":
    unittest.main()
