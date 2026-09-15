from types import SimpleNamespace

import numpy as np
import pytest

from emotv.application import EmotionClassifier, EmotionModelCatalog
from emotv.domain import CroppedFace
from emotv.infrastructure.vision.emotion_classifier import FerPlusEmotionClassifier, create_emotion_classifier
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import EmotionClassifier as LegacyClassifier


class Session:
    def get_inputs(self): return [SimpleNamespace(name="input")]
    def get_outputs(self): return [SimpleNamespace(name="output")]
    def run(self, outputs, inputs):
        tensor = inputs["input"]
        assert tensor.shape == (1, 1, 64, 64)
        assert tensor.dtype == np.float32
        assert tensor.max() == 255  # conserva el preprocesamiento anterior
        return [np.array([[0, 4, 0, 0, 0, 0, 0, 0]], dtype=np.float32)]


def test_default_factory_and_legacy_adapter(tmp_path, monkeypatch):
    path = tmp_path / "ferplus.onnx"
    path.write_bytes(b"test-model")
    import importlib
    module = importlib.import_module("emotv.infrastructure.vision.emotion_classifier.emotion_classifier")
    monkeypatch.setattr(module.ort, "InferenceSession", lambda *args, **kwargs: Session())
    classifier = create_emotion_classifier(model_path=path)
    assert isinstance(classifier, EmotionClassifier)
    assert isinstance(classifier, FerPlusEmotionClassifier)
    assert LegacyClassifier is FerPlusEmotionClassifier
    assert classifier.model == EmotionModelCatalog().default
    assert tuple(classifier.EMOTIONS) == classifier.model.emotion_labels
    emotion, confidence = classifier.predict(CroppedFace(np.full((64, 64), 255, np.uint8), (0, 0, 64, 64), 1))
    assert emotion == "happiness"
    assert 0 <= confidence <= 1


def test_unknown_model_does_not_fall_back():
    with pytest.raises(KeyError):
        create_emotion_classifier("unknown")


def test_missing_default_weights_is_explicit(tmp_path):
    with pytest.raises(FileNotFoundError, match="scripts/emotion/download_emotion_model.py"):
        create_emotion_classifier(model_path=tmp_path / "missing.onnx")
