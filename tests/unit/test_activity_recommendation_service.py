from __future__ import annotations

import unittest

from emotv.application import (
    ActivityCatalog,
    ActivityRecommendationService,
    DEFAULT_ACTIVITIES_BY_EMOTION,
)
from emotv.domain import Activity, PostureId


class ActivityRecommendationServiceTests(unittest.TestCase):
    def test_recommends_first_activity_for_sadness(self) -> None:
        activity = ActivityRecommendationService().recommend("sadness")

        self.assertIsNotNone(activity)
        assert activity is not None
        self.assertEqual(activity.id, "arms_up_5s")
        self.assertIs(activity.required_posture, PostureId.ARMS_UP)

    def test_returns_all_options_in_priority_order(self) -> None:
        activities = ActivityRecommendationService().recommend_all("sadness")

        self.assertEqual(
            tuple(activity.id for activity in activities),
            ("arms_up_5s", "arms_open_5s"),
        )

    def test_normalizes_emotion(self) -> None:
        activity = ActivityRecommendationService().recommend("  ANGER ")

        self.assertIsNotNone(activity)
        assert activity is not None
        self.assertEqual(activity.id, "arms_open_5s")

    def test_returns_none_for_emotion_without_association(self) -> None:
        service = ActivityRecommendationService()

        self.assertIsNone(service.recommend("neutral"))
        self.assertIsNone(service.recommend("unknown"))
        self.assertEqual(service.recommend_all("happiness"), ())

    def test_supports_custom_catalog_and_mapping(self) -> None:
        activity = Activity(
            id="custom_hands",
            name="Actividad personalizada",
            description="Coloca las manos en las caderas.",
            required_posture=PostureId.HANDS_ON_HIPS,
            duration_seconds=3.0,
        )
        service = ActivityRecommendationService(
            catalog=ActivityCatalog((activity,)),
            activities_by_emotion={"neutral": ("custom_hands",)},
        )

        self.assertIs(service.recommend("neutral"), activity)
        self.assertEqual(service.supported_emotions, {"neutral"})

    def test_rejects_mapping_to_missing_activity(self) -> None:
        with self.assertRaisesRegex(KeyError, "Actividad no encontrada"):
            ActivityRecommendationService(
                activities_by_emotion={"sadness": ("missing",)},
            )

    def test_rejects_empty_emotion(self) -> None:
        with self.assertRaises(ValueError):
            ActivityRecommendationService().recommend(" ")

    def test_default_mapping_covers_fer_plus_labels(self) -> None:
        expected = {
            "neutral",
            "happiness",
            "surprise",
            "sadness",
            "anger",
            "disgust",
            "fear",
            "contempt",
        }

        self.assertEqual(set(DEFAULT_ACTIVITIES_BY_EMOTION), expected)


if __name__ == "__main__":
    unittest.main()
