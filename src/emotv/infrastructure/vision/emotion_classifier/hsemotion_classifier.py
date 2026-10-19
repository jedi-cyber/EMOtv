"""HSEmotion enet_b0_8_best_afew en ONNX, sin el paquete hsemotion-onnx.

Contrato tomado del código oficial (av-savchenko/hsemotion-onnx,
hsemotion_onnx/facial_emotions.py, y sb-ai-lab/EmotiEffLib):
- recorte exacto del rostro detectado, sin margen;
- RGB, cv2.resize a 224x224, /255 y normalización con media y desviación de ImageNet;
- tensor NCHW float32 en la entrada "input"; salida de 8 logits;
- orden de clases: Anger, Contempt, Disgust, Fear, Happiness, Neutral, Sadness, Surprise.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.config import HSEMOTION_MODEL_PATH
from emotv.domain.cropped_face import CroppedFace
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import session_options


HSEMOTION_MODEL_ID = "hsemotion_enet_b0_8_best_afew"
# Orden de salida del modelo (idx_to_class de facial_emotions.py).
HSEMOTION_CLASSES = ("Anger", "Contempt", "Disgust", "Fear", "Happiness", "Neutral", "Sadness", "Surprise")
# Clases de HSEmotion -> claves de EMOtv.
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
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def preprocess(face_bgr: np.ndarray) -> np.ndarray:
    """Recorte BGR uint8 -> tensor (1, 3, 224, 224) como en facial_emotions.preprocess."""
    if face_bgr is None or face_bgr.size == 0 or face_bgr.dtype != np.uint8 or face_bgr.ndim != 3 or face_bgr.shape[2] != 3:
        raise ValueError("HSEmotion requiere un recorte BGR uint8 de tres canales")
    rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
    x = cv2.resize(rgb, (IMAGE_SIZE, IMAGE_SIZE)).astype(np.float32) / 255
    x = (x - MEAN) / STD
    return x.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)


class HSEmotionClassifier:
    """Clasificador local en CPU; las clases se devuelven con las claves de EMOtv."""

    # El recorte llega sin margen ni redimensionar y en color; el clasificador
    # aplica el resto del preprocesamiento oficial.
    face_preprocessor_options = dict(padding_ratio=0.0, target_size=None, grayscale=False, normalize=False)
    labels = tuple(HSEMOTION_TO_EMOTV[name] for name in HSEMOTION_CLASSES)

    def __init__(self, model_path: str | Path | None = None, intra_op_threads: int | None = None) -> None:
        self.model_path = Path(model_path) if model_path is not None else HSEMOTION_MODEL_PATH
        if not self.model_path.is_file() or self.model_path.stat().st_size == 0:
            raise FileNotFoundError("Modelo HSEmotion no instalado. Ejecuta python scripts/download_models.py")
        self.model = EmotionModelCatalog().get(HSEMOTION_MODEL_ID)
        self.session = ort.InferenceSession(str(self.model_path), sess_options=session_options(intra_op_threads),
                                            providers=["CPUExecutionProvider"])
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        if list(inputs[0].shape[1:]) != [3, IMAGE_SIZE, IMAGE_SIZE] or outputs[0].shape[-1] != len(HSEMOTION_CLASSES):
            raise RuntimeError("El archivo ONNX no corresponde a HSEmotion enet_b0_8")
        self.input_name = inputs[0].name
        self.output_name = outputs[0].name

    def predict(self, cropped_face: CroppedFace) -> tuple[str, float]:
        distribution = self.predict_distribution(cropped_face)
        emotion = max(distribution, key=distribution.__getitem__)
        return emotion, distribution[emotion]

    def predict_distribution(self, cropped_face: CroppedFace) -> dict[str, float]:
        logits = self.session.run([self.output_name], {self.input_name: preprocess(cropped_face.image)})[0][0]
        if logits.shape != (len(HSEMOTION_CLASSES),) or not np.isfinite(logits).all():
            raise ValueError("Salida HSEmotion inválida")
        exp = np.exp(logits - np.max(logits))
        probabilities = exp / exp.sum()
        return {label: float(value) for label, value in zip(self.labels, probabilities)}
