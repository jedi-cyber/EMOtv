"""HSEmotion enet_b0_8_best_afew: clases, preprocesamiento y recorte, sin pesos reales."""
from types import SimpleNamespace

import numpy as np
import pytest

from emotv.application.emotion_model_catalog import FERPLUS_LABELS, EmotionModelCatalog
from emotv.config import HSEMOTION_MODEL_PATH
from emotv.domain.cropped_face import CroppedFace
from emotv.infrastructure.vision.emotion_classifier import FerPlusEmotionClassifier, HardlyHumansEmotionClassifier
from emotv.infrastructure.vision.emotion_classifier.hsemotion_classifier import (
    HSEMOTION_CLASSES, HSEMOTION_MODEL_ID, HSEMOTION_TO_EMOTV, HSEmotionClassifier, preprocess,
)
from emotv.infrastructure.vision.face_detection.yunet_face_detector import FaceDetection
from emotv.infrastructure.vision.face_processing.face_preprocessor import FacePreprocessor


def test_classes_follow_official_order_and_map_to_emotv_keys():
    # idx_to_class de hsemotion_onnx/facial_emotions.py para modelos de 8 clases.
    assert HSEMOTION_CLASSES == ("Anger", "Contempt", "Disgust", "Fear", "Happiness", "Neutral", "Sadness", "Surprise")
    assert HSEmotionClassifier.labels == (
        "anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise")
    assert set(HSEMOTION_TO_EMOTV.values()) == set(FERPLUS_LABELS)
    assert EmotionModelCatalog().get(HSEMOTION_MODEL_ID).emotion_labels == FERPLUS_LABELS


def test_preprocess_converts_bgr_to_normalized_rgb_tensor():
    face = np.zeros((90, 70, 3), dtype=np.uint8)
    face[..., 0] = 255  # azul puro en BGR
    tensor = preprocess(face)
    assert tensor.shape == (1, 3, 224, 224) and tensor.dtype == np.float32
    # Canal 0 = rojo (0), canal 2 = azul (255): RGB con media y desviación de ImageNet.
    assert np.allclose(tensor[0, 0], (0 - 0.485) / 0.229)
    assert np.allclose(tensor[0, 1], (0 - 0.456) / 0.224)
    assert np.allclose(tensor[0, 2], (1 - 0.406) / 0.225)


@pytest.mark.parametrize("image", [np.zeros((64, 64), dtype=np.uint8), np.zeros((8, 8, 3), dtype=np.float32),
                                   np.zeros((0, 0, 3), dtype=np.uint8)])
def test_preprocess_rejects_non_bgr_crops(image):
    with pytest.raises(ValueError, match="BGR"):
        preprocess(image)


def _with_logits(logits):
    classifier = HSEmotionClassifier.__new__(HSEmotionClassifier)
    classifier.input_name, classifier.output_name = "input", "output"
    calls = []

    def run(outputs, feeds):
        calls.append(feeds["input"].shape)
        return [np.array([logits], dtype=np.float32)]

    classifier.session = SimpleNamespace(run=run)
    return classifier, calls


@pytest.mark.parametrize("index,expected", [(1, "contempt"), (4, "happiness"), (5, "neutral"), (7, "surprise")])
def test_prediction_uses_hsemotion_order(index, expected):
    logits = [0.0] * 8
    logits[index] = 4.0
    classifier, calls = _with_logits(logits)
    face = CroppedFace(np.full((40, 30, 3), 128, dtype=np.uint8), (0, 0, 30, 40), .9)
    distribution = classifier.predict_distribution(face)
    assert calls == [(1, 3, 224, 224)]
    assert set(distribution) == set(FERPLUS_LABELS)
    assert sum(distribution.values()) == pytest.approx(1.0)
    assert classifier.predict(face)[0] == expected


def test_invalid_output_is_rejected():
    classifier, _ = _with_logits([np.nan] * 8)
    with pytest.raises(ValueError, match="inválida"):
        classifier.predict_distribution(CroppedFace(np.zeros((10, 10, 3), dtype=np.uint8), (0, 0, 10, 10), 1))


def test_missing_weights_point_to_download_script(tmp_path):
    with pytest.raises(FileNotFoundError, match="download_models.py"):
        HSEmotionClassifier(model_path=tmp_path / "missing.onnx")


def test_each_model_declares_its_own_crop():
    ferplus = FerPlusEmotionClassifier.face_preprocessor_options
    hsemotion = HSEmotionClassifier.face_preprocessor_options
    assert ferplus == dict(padding_ratio=0.2, target_size=(64, 64), grayscale=True, normalize=False)
    # Recorte oficial de HSEmotion: el rectángulo detectado, sin margen y en color.
    assert hsemotion == dict(padding_ratio=0.0, target_size=None, grayscale=False, normalize=False)
    assert "padding_ratio" in HardlyHumansEmotionClassifier.face_preprocessor_options


def test_crops_differ_per_model_on_the_same_frame():
    frame = np.random.default_rng(1).integers(0, 256, (240, 320, 3), dtype=np.uint8)
    detection = FaceDetection(100, 60, 80, 100, .95)
    ferplus = FacePreprocessor(**FerPlusEmotionClassifier.face_preprocessor_options).process(frame, detection)
    hsemotion = FacePreprocessor(**HSEmotionClassifier.face_preprocessor_options).process(frame, detection)
    assert ferplus.image.shape == (64, 64)
    assert hsemotion.image.shape == (100, 80, 3) and hsemotion.image.dtype == np.uint8
    assert np.array_equal(hsemotion.image, frame[60:160, 100:180])


@pytest.mark.skipif(not HSEMOTION_MODEL_PATH.is_file(), reason="Pesos HSEmotion no instalados (scripts/download_models.py)")
def test_real_weights_load_and_return_eight_classes():
    classifier = HSEmotionClassifier()
    face = CroppedFace(np.full((120, 100, 3), 128, dtype=np.uint8), (0, 0, 100, 120), 1)
    distribution = classifier.predict_distribution(face)
    assert set(distribution) == set(FERPLUS_LABELS)
    assert sum(distribution.values()) == pytest.approx(1.0, abs=1e-5)
