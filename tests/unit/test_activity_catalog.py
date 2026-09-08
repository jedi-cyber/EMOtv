from __future__ import annotations

import unittest

from emotv.application import ActivityCatalog, DEFAULT_ACTIVITIES
from emotv.domain import Activity, PostureId


class ActivityTests(unittest.TestCase):
    def test_normalizes_text_and_posture_identifier(self) -> None:
        activity = Activity(
            id="  custom  ",
            name="  Actividad  ",
            description="  Instrucción  ",
            required_posture="arms_open",
            duration_seconds=3,
        )

        self.assertEqual(activity.id, "custom")
        self.assertEqual(activity.name, "Actividad")
        self.assertIs(activity.required_posture, PostureId.ARMS_OPEN)
        self.assertEqual(activity.duration_seconds, 3.0)

    def test_rejects_invalid_activity_values(self) -> None:
        valid = {
            "id": "activity",
            "name": "Actividad",
            "description": "Instrucción",
            "required_posture": PostureId.ARMS_UP,
            "duration_seconds": 5.0,
        }
        invalid_overrides = (
            {"id": " "},
            {"name": " "},
            {"description": " "},
            {"duration_seconds": 0.0},
            {"repetitions": 0},
            {"repetitions": 1.5},
        )

        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                Activity(**(valid | overrides))

    def test_rejects_unknown_posture(self) -> None:
        with self.assertRaises(ValueError):
            Activity(
                id="unknown",
                name="Actividad",
                description="Instrucción",
                required_posture="unknown",
                duration_seconds=5.0,
            )


class ActivityCatalogTests(unittest.TestCase):
    def test_default_catalog_has_one_activity_per_implemented_posture(self) -> None:
        catalog = ActivityCatalog()

        self.assertEqual(len(catalog.list_all()), 3)
        for posture_id in (
            PostureId.ARMS_UP,
            PostureId.ARMS_OPEN,
            PostureId.HANDS_ON_HIPS,
        ):
            with self.subTest(posture_id=posture_id):
                self.assertEqual(len(catalog.for_posture(posture_id)), 1)

    def test_get_returns_activity_by_stable_identifier(self) -> None:
        activity = ActivityCatalog().get("arms_up_5s")

        self.assertEqual(activity.name, "Elevación de brazos")
        self.assertIs(activity.required_posture, PostureId.ARMS_UP)

    def test_catalog_returns_immutable_collections(self) -> None:
        catalog = ActivityCatalog()

        self.assertIsInstance(catalog.ids, tuple)
        self.assertIsInstance(catalog.list_all(), tuple)
        self.assertIsInstance(catalog.for_posture("arms_up"), tuple)

    def test_catalog_rejects_duplicate_ids(self) -> None:
        with self.assertRaises(ValueError):
            ActivityCatalog((DEFAULT_ACTIVITIES[0], DEFAULT_ACTIVITIES[0]))

    def test_get_rejects_unknown_activity(self) -> None:
        with self.assertRaisesRegex(KeyError, "Actividad no encontrada"):
            ActivityCatalog().get("unknown")

    def test_adds_updates_and_removes_activity(self) -> None:
        catalog = ActivityCatalog(())
        activity = Activity(
            "custom", "Actividad", "Descripción", PostureId.ARMS_OPEN, 3.0
        )
        catalog.add(activity)
        updated = Activity(
            "custom", "Actualizada", "Nueva descripción", PostureId.ARMS_UP, 5.0
        )

        self.assertEqual(catalog.update("custom", updated), updated)
        self.assertEqual(catalog.remove("custom"), updated)
        self.assertEqual(catalog.list_all(), ())

    def test_rejects_duplicate_and_unknown_mutations(self) -> None:
        catalog = ActivityCatalog()

        with self.assertRaises(ValueError):
            catalog.add(DEFAULT_ACTIVITIES[0])
        with self.assertRaises(KeyError):
            catalog.remove("missing")


if __name__ == "__main__":
    unittest.main()
