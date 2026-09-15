from __future__ import annotations

import unittest

from emotv.application import EmotionClassifier
from emotv.domain import CroppedFace
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import (
    EmotionClassifier as OnnxEmotionClassifier,
)


class FakeEmotionClassifier:
    def predict(self, cropped_face: CroppedFace) -> tuple[str, float]:
        return "neutral", 0.9


class InvalidEmotionClassifier:
    pass


class EmotionClassifierContractTests(unittest.TestCase):
    def test_structural_implementation_satisfies_contract(self) -> None:
        self.assertIsInstance(FakeEmotionClassifier(), EmotionClassifier)

    def test_existing_onnx_adapter_satisfies_contract(self) -> None:
        classifier = OnnxEmotionClassifier.__new__(OnnxEmotionClassifier)

        self.assertIsInstance(classifier, EmotionClassifier)

    def test_rejects_object_without_predict_operation(self) -> None:
        self.assertNotIsInstance(InvalidEmotionClassifier(), EmotionClassifier)


if __name__ == "__main__":
    unittest.main()
