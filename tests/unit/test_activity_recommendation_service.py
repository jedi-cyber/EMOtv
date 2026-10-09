from __future__ import annotations

import unittest

from emotv.application import (
    ActivityCatalog,
    ActivityRecommendationService,
    DEFAULT_ACTIVITIES_BY_EMOTION,
)
from emotv.domain import Activity, PostureId
from emotv.domain.activity import ActivityStep
from emotv.infrastructure.persistence import InMemoryRecommendationRepository

LOGGER = "emotv.application.activity_recommendation_service"


def two_step(activity_id: str) -> Activity:
    return Activity(
        activity_id, "Actividad personalizada", "Coloca las manos en las caderas.",
        PostureId.HANDS_ON_HIPS, 3.0,
        steps=(ActivityStep(PostureId.HANDS_ON_HIPS, "Manos en las caderas", 3),
               ActivityStep(PostureId.ARMS_OPEN, "Abre los brazos", 3)),
    )


SINGLE = Activity("single", "Un paso", "Eleva los brazos", PostureId.ARMS_UP, 3)


class ActivityRecommendationServiceTests(unittest.TestCase):
    def test_recommends_first_activity_for_sadness(self) -> None:
        activity = ActivityRecommendationService().recommend("sadness")

        self.assertIsNotNone(activity)
        assert activity is not None
        self.assertEqual(activity.id, "morning_mobility")
        self.assertIs(activity.required_posture, PostureId.ARMS_OPEN)

    def test_returns_all_options_in_priority_order(self) -> None:
        activities = ActivityRecommendationService().recommend_all("sadness")

        self.assertEqual(
            tuple(activity.id for activity in activities),
            ("morning_mobility", "open_and_reach"),
        )

    def test_every_default_recommendation_has_multiple_steps(self) -> None:
        service = ActivityRecommendationService()
        for emotion in DEFAULT_ACTIVITIES_BY_EMOTION:
            activities = service.recommend_all(emotion)
            self.assertGreater(len(activities), 0)
            for activity in activities:
                self.assertGreaterEqual(len(activity.steps), 2)

    def test_normalizes_emotion(self) -> None:
        activity = ActivityRecommendationService().recommend("  ANGER ")

        self.assertIsNotNone(activity)
        assert activity is not None
        self.assertEqual(activity.id, "upper_body_flow")

    def test_returns_none_for_emotion_without_association(self) -> None:
        service = ActivityRecommendationService()

        self.assertIsNotNone(service.recommend("neutral"))
        self.assertIsNone(service.recommend("unknown"))
        self.assertIsNone(service.recommend_varied("unknown"))

    def test_varied_recommendation_avoids_the_excluded_activity(self) -> None:
        service = ActivityRecommendationService()
        for _ in range(20):
            chosen = service.recommend_varied("sadness", exclude_ids=("morning_mobility",))
            assert chosen is not None
            self.assertEqual(chosen.id, "open_and_reach")

    def test_varied_recommendation_falls_back_when_everything_is_excluded(self) -> None:
        chosen = ActivityRecommendationService().recommend_varied(
            "sadness", exclude_ids=("morning_mobility", "open_and_reach"),
        )
        assert chosen is not None
        self.assertIn(chosen.id, {"morning_mobility", "open_and_reach"})

    def test_has_no_shared_mutable_state_between_calls(self) -> None:
        # Sin memoria del proceso: la variación depende solo de exclude_ids.
        service = ActivityRecommendationService(
            catalog=ActivityCatalog((two_step("only"),)),
            activities_by_emotion={"neutral": ("only",)},
        )
        self.assertEqual(service.recommend_varied("neutral").id, "only")
        self.assertEqual(service.recommend_varied("neutral").id, "only")
        self.assertFalse(any(isinstance(value, dict) for value in vars(service).values()))

    def test_supports_custom_catalog_and_mapping(self) -> None:
        activity = two_step("custom_hands")
        service = ActivityRecommendationService(
            catalog=ActivityCatalog((activity,)),
            activities_by_emotion={"neutral": ("custom_hands",)},
        )

        self.assertIs(service.recommend("neutral"), activity)

    def test_missing_activity_is_skipped_with_warning(self) -> None:
        service = ActivityRecommendationService(
            catalog=ActivityCatalog((two_step("valid"),)),
            activities_by_emotion={"sadness": ("missing", "valid")},
        )
        with self.assertLogs(LOGGER, "WARNING") as logs:
            self.assertEqual([item.id for item in service.recommend_all("sadness")], ["valid"])
        self.assertIn("missing", logs.output[0])

    def test_single_step_activity_is_skipped_with_warning(self) -> None:
        service = ActivityRecommendationService(
            catalog=ActivityCatalog((SINGLE, two_step("valid"))),
            activities_by_emotion={"neutral": ("single", "valid")},
        )
        with self.assertLogs(LOGGER, "WARNING") as logs:
            self.assertEqual(service.recommend("neutral").id, "valid")
        self.assertIn("single", logs.output[0])

    def test_expression_without_valid_candidates_returns_none_without_raising(self) -> None:
        service = ActivityRecommendationService(
            catalog=ActivityCatalog((SINGLE,)),
            activities_by_emotion={"neutral": ("single", "missing")},
        )
        with self.assertLogs(LOGGER, "WARNING"):
            self.assertIsNone(service.recommend_varied("neutral"))

    def test_reads_associations_at_call_time(self) -> None:
        repository = InMemoryRecommendationRepository({"fear": ("first",)})
        service = ActivityRecommendationService(
            catalog=ActivityCatalog((two_step("first"), two_step("second"))), source=repository,
        )
        self.assertEqual(service.recommend("fear").id, "first")
        repository.replace("fear", ("second",))
        self.assertEqual(service.recommend("fear").id, "second")

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
