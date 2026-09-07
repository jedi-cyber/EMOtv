from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np

from emotv.application.pose_service import PoseService
from emotv.domain.pose_landmarks import PoseLandmark, PoseLandmarks
from emotv.domain.pose_result import PoseResult
from emotv.domain.posture_id import PostureId
from emotv.domain.posture_result import PostureResult
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

    def test_pose_service_validates_selected_posture(self) -> None:
        pose = make_pose(wrists_y=0.2)
        detector = FakePoseDetector(PoseResult(detected=True, landmarks=pose))
        service = PoseService(detector=detector)

        result = service.validate(
            np.zeros((10, 10, 3), dtype=np.uint8),
            PostureId.ARMS_UP,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.detected)
        self.assertIsNotNone(service.last_pose_result)
        assert service.last_pose_result is not None
        self.assertIs(service.last_pose_result.landmarks, pose)

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

    def test_generic_validation_returns_measurements(self) -> None:
        result = PostureValidator().validate(
            make_pose(wrists_y=0.2),
            PostureId.ARMS_UP,
        )

        self.assertTrue(result.detected)
        self.assertEqual(result.confidence, 1.0)
        self.assertAlmostEqual(result.measurements["left_elbow_angle"], 180.0)
        self.assertEqual(result.failed_rules, ())

    def test_generic_validation_reports_failed_rules(self) -> None:
        result = PostureValidator().validate(
            make_pose(wrists_y=0.6),
            "arms_up",
        )

        self.assertFalse(result.detected)
        self.assertIn("left_wrist_above_shoulder", result.failed_rules)
        self.assertIn("right_wrist_above_shoulder", result.failed_rules)
        self.assertLess(result.confidence, 1.0)

    def test_arms_up_reports_only_the_side_below_shoulder(self) -> None:
        pose = make_pose(wrists_y=0.2)
        pose = replace(
            pose,
            right_elbow=PoseLandmark(0.6, 0.5),
            right_wrist=PoseLandmark(0.6, 0.6),
        )

        result = PostureValidator().validate(pose, PostureId.ARMS_UP)

        self.assertNotIn("left_wrist_above_shoulder", result.failed_rules)
        self.assertIn("right_wrist_above_shoulder", result.failed_rules)

    def test_arms_up_accepts_visibility_at_exact_threshold(self) -> None:
        pose = make_pose(wrists_y=0.2)
        pose = replace(
            pose,
            left_wrist=replace(pose.left_wrist, visibility=0.5),
        )

        self.assertTrue(PostureValidator().validate(pose, "arms_up").detected)

    def test_arms_up_accepts_elbow_at_configured_inclusive_limit(self) -> None:
        pose = make_pose(wrists_y=0.2)
        pose = replace(pose, left_elbow=PoseLandmark(0.5, 0.3))
        validator = PostureValidator(
            ArmsUpThresholds(elbow_straight_tolerance_degrees=90.0),
        )

        result = validator.validate(pose, PostureId.ARMS_UP)

        self.assertTrue(result.detected)
        self.assertAlmostEqual(result.measurements["left_elbow_angle"], 90.0)

    def test_unimplemented_posture_has_explicit_error(self) -> None:
        with self.assertRaises(NotImplementedError):
            PostureValidator().validate(
                make_pose(wrists_y=0.2),
                PostureId.ARMS_FORWARD,
            )

    def test_can_register_an_additional_posture(self) -> None:
        validator = PostureValidator()

        def arms_forward_evaluator(pose: PoseLandmarks) -> PostureResult:
            return PostureResult(
                PostureId.ARMS_FORWARD,
                detected=True,
                confidence=0.8,
            )

        validator.register(PostureId.ARMS_FORWARD, arms_forward_evaluator)
        result = validator.validate(make_pose(wrists_y=0.4), "arms_forward")

        self.assertTrue(result.detected)
        self.assertIs(result.posture_id, PostureId.ARMS_FORWARD)
        self.assertIn(PostureId.ARMS_FORWARD, validator.supported_postures)

    def test_rejects_result_for_a_different_posture(self) -> None:
        validator = PostureValidator()
        validator.register(
            PostureId.ARMS_FORWARD,
            lambda pose: PostureResult(PostureId.SQUAT, detected=True),
        )

        with self.assertRaises(ValueError):
            validator.validate(make_pose(wrists_y=0.4), PostureId.ARMS_FORWARD)


if __name__ == "__main__":
    unittest.main()
