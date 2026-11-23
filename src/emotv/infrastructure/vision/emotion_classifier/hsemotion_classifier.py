"""Modelos ONNX de EmotiEffLib (antes HSEmotion), sin instalar sus paquetes.

Contrato tomado del código oficial (av-savchenko/hsemotion-onnx,
hsemotion_onnx/facial_emotions.py, y sb-ai-lab/EmotiEffLib,
emotiefflib/facial_analysis.py):
- recorte exacto del rostro detectado, sin margen;
- RGB, cv2.resize al tamaño del modelo, /255 y normalización con media y desviación de ImageNet;
- tensor NCHW float32 en la entrada "input"; salida de 8 logits;
- orden de clases: Anger, Contempt, Disgust, Fear, Happiness, Neutral, Sadness, Surprise.

Variantes integradas (mismo repositorio y commit, licencia Apache-2.0):
- enet_b0_8_best_afew (HSEmotion), 224x224: predeterminado en vivo;
- enet_b2_8 (EmotiEffLib EfficientNet-B2), 260x260: más preciso en AffectNet y más pesado.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.config import EMOTIEFFLIB_B2_MODEL_PATH, HSEMOTION_MODEL_PATH
from emotv.domain.cropped_face import CroppedFace
from emotv.domain.expression_info import restrict_to_estimated
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import session_options


HSEMOTION_MODEL_ID = "hsemotion_enet_b0_8_best_afew"
EMOTIEFFLIB_B2_MODEL_ID = "emotiefflib_enet_b2_8"
# Orden de salida de los modelos de 8 clases (idx_to_emotion_class de EmotiEffLib).
HSEMOTION_CLASSES = ("Anger", "Contempt", "Disgust", "Fear", "Happiness", "Neutral", "Sadness", "Surprise")
# Clases de EmotiEffLib -> claves de EMOtv.
HSEMOTION_TO_EMOTV = {
    "Anger": "anger",
    "Contempt": "contempt",
    "Disgust": "disgust",
    "Fear": "fear",
    "Happiness": "happiness",
    "Neutral": "neutral",
    "Sadness": "sadness",
    "Surprise": "surprise",
}
IMAGE_SIZE = 224
B2_IMAGE_SIZE = 260
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def preprocess(face_bgr: np.ndarray, size: int = IMAGE_SIZE) -> np.ndarray:
    """Recorte BGR uint8 -> tensor (1, 3, size, size) como en facial_analysis._preprocess."""
    if face_bgr is None or face_bgr.size == 0 or face_bgr.dtype != np.uint8 or face_bgr.ndim != 3 or face_bgr.shape[2] != 3:
        raise ValueError("EmotiEffLib requiere un recorte BGR uint8 de tres canales")
    rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
    x = cv2.resize(rgb, (size, size)).astype(np.float32) / 255
    x = (x - MEAN) / STD
    return x.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)


class EmotiEffLibClassifier:
    """Clasificador local en CPU; las clases se devuelven con las claves de EMOtv."""

    model_id = HSEMOTION_MODEL_ID
    image_size = IMAGE_SIZE
    default_path = HSEMOTION_MODEL_PATH
    display_name = "HSEmotion enet_b0_8"
    # El recorte llega sin margen ni redimensionar y en color; el clasificador
    # aplica el resto del preprocesamiento oficial.
    face_preprocessor_options = dict(padding_ratio=0.0, target_size=None, grayscale=False, normalize=False)
    labels = tuple(HSEMOTION_TO_EMOTV[name] for name in HSEMOTION_CLASSES)

    def __init__(self, model_path: str | Path | None = None, intra_op_threads: int | None = None) -> None:
        self.model_path = Path(model_path) if model_path is not None else self.default_path
        if not self.model_path.is_file() or self.model_path.stat().st_size == 0:
            raise FileNotFoundError(f"Modelo {self.display_name} no instalado. Ejecuta python scripts/download_models.py")
        self.model = EmotionModelCatalog().get(self.model_id)
        self.session = ort.InferenceSession(str(self.model_path), sess_options=session_options(intra_op_threads),
                                            providers=["CPUExecutionProvider"])
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        size = self.image_size
        if list(inputs[0].shape[1:]) != [3, size, size] or outputs[0].shape[-1] != len(HSEMOTION_CLASSES):
            raise RuntimeError(f"El archivo ONNX no corresponde a {self.display_name}")
        self.input_name = inputs[0].name
        self.output_name = outputs[0].name

    def predict(self, cropped_face: CroppedFace) -> tuple[str, float]:
        distribution = self.predict_distribution(cropped_face)
        emotion = max(distribution, key=distribution.__getitem__)
        return emotion, distribution[emotion]

    def predict_distribution(self, cropped_face: CroppedFace) -> dict[str, float]:
        tensor = preprocess(cropped_face.image, self.image_size)
        logits = self.session.run([self.output_name], {self.input_name: tensor})[0][0]
        if logits.shape != (len(HSEMOTION_CLASSES),) or not np.isfinite(logits).all():
            raise ValueError(f"Salida de {self.display_name} inválida")
        exp = np.exp(logits - np.max(logits))
        probabilities = exp / exp.sum()
        return restrict_to_estimated({label: float(value) for label, value in zip(self.labels, probabilities)})


class HSEmotionClassifier(EmotiEffLibClassifier):
    """HSEmotion enet_b0_8_best_afew (224x224): predeterminado en vivo."""


class EmotiEffLibB2Classifier(EmotiEffLibClassifier):
    """EmotiEffLib enet_b2_8 (260x260)."""

    model_id = EMOTIEFFLIB_B2_MODEL_ID
    image_size = B2_IMAGE_SIZE
    default_path = EMOTIEFFLIB_B2_MODEL_PATH
    display_name = "EmotiEffLib enet_b2_8"
