from __future__ import annotations

import unittest

from emotv.domain import PostureId, PostureResult


class PostureModelsTests(unittest.TestCase):
    def test_posture_ids_have_stable_serializable_values(self) -> None:
        self.assertEqual(PostureId.ARMS_UP.value, "arms_up")
        self.assertEqual(PostureId.HANDS_ON_HIPS.value, "hands_on_hips")

    def test_result_accepts_string_identifier_and_exposes_compatibility_name(self) -> None:
        result = PostureResult(posture_id="arms_open", detected=True)

        self.assertIs(result.posture_id, PostureId.ARMS_OPEN)
        self.assertEqual(result.name, "arms_open")
        self.assertTrue(result.is_valid)

    def test_result_preserves_measurements_and_failed_rules(self) -> None:
        measurements = {"left_elbow_angle": 90.0}
        failed_rules = ["left_elbow_extended"]
        result = PostureResult(
            posture_id=PostureId.ARMS_UP,
            detected=False,
            confidence=0.75,
            measurements=measurements,
            failed_rules=failed_rules,
        )
        measurements["left_elbow_angle"] = 180.0
        failed_rules.append("wrists_above_shoulders")

        self.assertEqual(result.measurements["left_elbow_angle"], 90.0)
        self.assertEqual(result.failed_rules, ("left_elbow_extended",))

    def test_result_rejects_unknown_identifier(self) -> None:
        with self.assertRaises(ValueError):
            PostureResult(posture_id="unknown", detected=False)

    def test_result_rejects_confidence_outside_normalized_range(self) -> None:
        with self.assertRaises(ValueError):
            PostureResult(
                posture_id=PostureId.SQUAT,
                detected=False,
                confidence=1.1,
            )


if __name__ == "__main__":
    unittest.main()
