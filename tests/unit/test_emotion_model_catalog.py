from __future__ import annotations

import unittest

from emotv.application import DEFAULT_EMOTION_MODELS, EmotionModelCatalog
from emotv.domain import EmotionModel


def make_model(model_id: str, *, is_default: bool = False) -> EmotionModel:
    return EmotionModel(
        id=model_id,
        name=f"Modelo {model_id}",
        description="Modelo facial para pruebas.",
        version="1.0",
        input_size=(64, 64),
        emotion_labels=("neutral", "happiness"),
        is_default=is_default,
    )


class EmotionModelTests(unittest.TestCase):
    def test_normalizes_public_metadata(self) -> None:
        model = EmotionModel(
            " model ",
            " Modelo ",
            " Descripción ",
            " 1.0 ",
            (64, 64),
            (" Neutral ", "HAPPINESS"),
            True,
        )

        self.assertEqual(model.id, "model")
        self.assertEqual(model.emotion_labels, ("neutral", "happiness"))
        self.assertTrue(model.is_default)

    def test_rejects_invalid_metadata(self) -> None:
        with self.assertRaises(ValueError):
            make_model(" ")
        with self.assertRaises(ValueError):
            EmotionModel("x", "X", "D", "1", (0, 64), ("neutral",))
        with self.assertRaises(ValueError):
            EmotionModel("x", "X", "D", "1", (64, 64), ())
        with self.assertRaises(ValueError):
            EmotionModel("x", "X", "D", "1", (64, 64), ("fear", "FEAR"))


class EmotionModelCatalogTests(unittest.TestCase):
    def test_exposes_current_model_as_default(self) -> None:
        catalog = EmotionModelCatalog()

        self.assertEqual(catalog.default.id, "ferplus_onnx")
        self.assertIs(catalog.get(), catalog.default)
        self.assertEqual(catalog.list_all(), DEFAULT_EMOTION_MODELS)

    def test_selects_model_by_normalized_id(self) -> None:
        default = make_model("standard", is_default=True)
        accurate = make_model("accurate")
        catalog = EmotionModelCatalog((default, accurate))

        self.assertIs(catalog.get(" ACCURATE "), accurate)
        self.assertEqual(catalog.ids, ("standard", "accurate"))

    def test_rejects_invalid_catalog_configuration(self) -> None:
        default = make_model("standard", is_default=True)

        with self.assertRaises(ValueError):
            EmotionModelCatalog((default, default))
        with self.assertRaises(ValueError):
            EmotionModelCatalog((make_model("standard"),))
        with self.assertRaises(ValueError):
            EmotionModelCatalog((default, make_model("other", is_default=True)))

    def test_empty_catalog_has_no_default(self) -> None:
        catalog = EmotionModelCatalog(())

        self.assertEqual(catalog.list_all(), ())
        with self.assertRaises(LookupError):
            _ = catalog.default

    def test_rejects_unknown_model(self) -> None:
        with self.assertRaisesRegex(KeyError, "Modelo de emociones no encontrado"):
            EmotionModelCatalog().get("unknown")


if __name__ == "__main__":
    unittest.main()
