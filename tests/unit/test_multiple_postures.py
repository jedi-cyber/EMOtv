from __future__ import annotations

import unittest
from dataclasses import replace

from emotv.domain import PoseLandmark, PoseLandmarks, PostureId
from emotv.infrastructure.vision.movement_analysis import (
    ArmsOpenThresholds,
    HandsOnHipsThresholds,
    PostureValidator,
)
from scripts.poses.run_posture_test import (
    KEY_TO_POSTURE,
    POSTURE_PRESENTATIONS,
    build_parser,
    diagnostic_lines,
)


def base_pose() -> PoseLandmarks:
    point = PoseLandmark(0.5, 0.5)
    return PoseLandmarks(
        nose=PoseLandmark(0.5, 0.1),
        left_shoulder=PoseLandmark(0.35, 0.3),
        right_shoulder=PoseLandmark(0.65, 0.3),
        left_elbow=point,
        right_elbow=point,
        left_wrist=point,
        right_wrist=point,
        left_hip=PoseLandmark(0.4, 0.6),
        right_hip=PoseLandmark(0.6, 0.6),
        left_knee=PoseLandmark(0.4, 0.8),
        right_knee=PoseLandmark(0.6, 0.8),
        left_ankle=PoseLandmark(0.4, 0.95),
        right_ankle=PoseLandmark(0.6, 0.95),
    )


def arms_open_pose() -> PoseLandmarks:
    return replace(
        base_pose(),
        left_elbow=PoseLandmark(0.2, 0.3),
        right_elbow=PoseLandmark(0.8, 0.3),
        left_wrist=PoseLandmark(0.05, 0.3),
        right_wrist=PoseLandmark(0.95, 0.3),
    )


def hands_on_hips_pose() -> PoseLandmarks:
    return replace(
        base_pose(),
        left_elbow=PoseLandmark(0.2, 0.45),
        right_elbow=PoseLandmark(0.8, 0.45),
        left_wrist=PoseLandmark(0.4, 0.6),
        right_wrist=PoseLandmark(0.6, 0.6),
    )


class MultiplePosturesTests(unittest.TestCase):
    def test_posture_script_defaults_to_arms_up(self) -> None:
        arguments = build_parser().parse_args([])

        self.assertEqual(arguments.posture, PostureId.ARMS_UP.value)

    def test_posture_script_accepts_each_supported_posture(self) -> None:
        validator = PostureValidator()

        self.assertEqual(set(POSTURE_PRESENTATIONS), set(validator.supported_postures))
        for posture_id in validator.supported_postures:
            with self.subTest(posture_id=posture_id):
                arguments = build_parser().parse_args(
                    ["--posture", posture_id.value],
                )
                self.assertEqual(arguments.posture, posture_id.value)

    def test_keyboard_shortcuts_select_the_three_postures(self) -> None:
        self.assertEqual(
            set(KEY_TO_POSTURE.values()),
            set(PostureValidator().supported_postures),
        )

    def test_three_postures_are_registered(self) -> None:
        self.assertEqual(
            PostureValidator().supported_postures,
            {
                PostureId.ARMS_UP,
                PostureId.ARMS_OPEN,
                PostureId.HANDS_ON_HIPS,
            },
        )

    def test_detects_arms_open(self) -> None:
        result = PostureValidator().validate(arms_open_pose(), PostureId.ARMS_OPEN)

        self.assertTrue(result.detected)
        self.assertEqual(result.confidence, 1.0)
        self.assertAlmostEqual(result.measurements["left_elbow_angle"], 180.0)
        self.assertTrue(any("Codos" in line for line in diagnostic_lines(result)))

    def test_arms_open_rejects_wrist_at_wrong_height(self) -> None:
        pose = arms_open_pose()
        pose = replace(pose, left_wrist=replace(pose.left_wrist, y=0.5))

        result = PostureValidator().validate(pose, PostureId.ARMS_OPEN)

        self.assertFalse(result.detected)
        self.assertIn("left_wrist_at_shoulder_height", result.failed_rules)

    def test_arms_open_rejects_insufficient_lateral_extension(self) -> None:
        pose = arms_open_pose()
        pose = replace(
            pose,
            left_elbow=PoseLandmark(0.325, 0.3),
            left_wrist=PoseLandmark(0.30, 0.3),
        )

        result = PostureValidator().validate(pose, PostureId.ARMS_OPEN)

        self.assertIn("left_arm_open_laterally", result.failed_rules)

    def test_arms_open_rejects_bent_elbow(self) -> None:
        pose = arms_open_pose()
        pose = replace(pose, right_elbow=PoseLandmark(0.8, 0.45))

        result = PostureValidator().validate(pose, PostureId.ARMS_OPEN)

        self.assertIn("right_elbow_extended", result.failed_rules)

    def test_arms_open_rejects_hidden_wrist(self) -> None:
        pose = arms_open_pose()
        pose = replace(
            pose,
            right_wrist=replace(pose.right_wrist, visibility=0.49),
        )

        result = PostureValidator().validate(pose, PostureId.ARMS_OPEN)

        self.assertIn("upper_body_visible", result.failed_rules)

    def test_arms_open_supports_mirrored_coordinates(self) -> None:
        pose = arms_open_pose()
        pose = replace(
            pose,
            left_shoulder=replace(pose.left_shoulder, x=0.65),
            right_shoulder=replace(pose.right_shoulder, x=0.35),
            left_elbow=replace(pose.left_elbow, x=0.8),
            right_elbow=replace(pose.right_elbow, x=0.2),
            left_wrist=replace(pose.left_wrist, x=0.95),
            right_wrist=replace(pose.right_wrist, x=0.05),
        )

        self.assertTrue(
            PostureValidator().validate(pose, PostureId.ARMS_OPEN).detected
        )

    def test_arms_open_tolerance_is_configurable(self) -> None:
        pose = arms_open_pose()
        pose = replace(
            pose,
            left_elbow=replace(pose.left_elbow, y=0.345),
            left_wrist=replace(pose.left_wrist, y=0.39),
        )
        validator = PostureValidator(
            arms_open_thresholds=ArmsOpenThresholds(wrist_height_tolerance=0.1),
        )

        result = validator.validate(pose, PostureId.ARMS_OPEN)

        self.assertTrue(result.detected)

    def test_detects_hands_on_hips(self) -> None:
        result = PostureValidator().validate(
            hands_on_hips_pose(),
            PostureId.HANDS_ON_HIPS,
        )

        self.assertTrue(result.detected)
        self.assertEqual(result.confidence, 1.0)
        self.assertAlmostEqual(result.measurements["left_wrist_hip_distance"], 0.0)

    def test_hands_on_hips_rejects_distant_hand(self) -> None:
        pose = hands_on_hips_pose()
        pose = replace(pose, right_wrist=PoseLandmark(0.9, 0.1))

        result = PostureValidator().validate(pose, PostureId.HANDS_ON_HIPS)

        self.assertFalse(result.detected)
        self.assertIn("right_hand_near_hip", result.failed_rules)

    def test_hands_on_hips_rejects_hidden_landmark(self) -> None:
        pose = hands_on_hips_pose()
        pose = replace(
            pose,
            left_hip=replace(pose.left_hip, visibility=0.1),
        )

        result = PostureValidator().validate(pose, PostureId.HANDS_ON_HIPS)

        self.assertFalse(result.detected)
        self.assertIn("upper_body_and_hips_visible", result.failed_rules)

    def test_hands_on_hips_rejects_straight_elbow(self) -> None:
        pose = hands_on_hips_pose()
        pose = replace(
            pose,
            left_shoulder=PoseLandmark(0.4, 0.2),
            left_elbow=PoseLandmark(0.4, 0.4),
        )

        result = PostureValidator().validate(pose, PostureId.HANDS_ON_HIPS)

        self.assertIn("left_elbow_bent", result.failed_rules)

    def test_hands_on_hips_rejects_inward_elbow(self) -> None:
        pose = hands_on_hips_pose()
        pose = replace(pose, left_elbow=PoseLandmark(0.45, 0.45))

        result = PostureValidator().validate(pose, PostureId.HANDS_ON_HIPS)

        self.assertIn("left_elbow_outward", result.failed_rules)

    def test_hands_on_hips_supports_mirrored_coordinates(self) -> None:
        pose = hands_on_hips_pose()
        pose = replace(
            pose,
            left_shoulder=replace(pose.left_shoulder, x=0.65),
            right_shoulder=replace(pose.right_shoulder, x=0.35),
            left_elbow=replace(pose.left_elbow, x=0.8),
            right_elbow=replace(pose.right_elbow, x=0.2),
            left_hip=replace(pose.left_hip, x=0.6),
            right_hip=replace(pose.right_hip, x=0.4),
            left_wrist=replace(pose.left_wrist, x=0.6),
            right_wrist=replace(pose.right_wrist, x=0.4),
        )

        self.assertTrue(
            PostureValidator().validate(pose, PostureId.HANDS_ON_HIPS).detected
        )

    def test_hands_on_hips_distance_is_configurable(self) -> None:
        pose = hands_on_hips_pose()
        pose = replace(pose, left_wrist=PoseLandmark(0.5, 0.6))
        validator = PostureValidator(
            hands_on_hips_thresholds=HandsOnHipsThresholds(
                wrist_hip_distance_tolerance=0.11,
            ),
        )

        self.assertTrue(
            validator.validate(pose, PostureId.HANDS_ON_HIPS).detected
        )


if __name__ == "__main__":
    unittest.main()
