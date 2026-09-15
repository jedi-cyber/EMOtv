from __future__ import annotations

from pathlib import Path
import numpy as np
import cv2
import onnxruntime as ort

from emotv.config import EMOTION_MODEL_PATH
from emotv.application.emotion_model_catalog import EmotionModelCatalog, FERPLUS_LABELS
from emotv.domain.cropped_face import CroppedFace


class FerPlusEmotionClassifier:
    """
    Clasificador de emociones basado en el modelo FER+ (ONNX).

    Responsabilidades:
    - Cargar el modelo ONNX.
    - Ejecutar inferencia sobre imágenes de rostros preprocesadas.
    - Devolver la emoción dominante y su confianza.
    """

    # Mapeo de índices a emociones (según FER+)
    EMOTIONS = list(FERPLUS_LABELS)

    def __init__(
        self,
        model_path: str | Path | None = None,
        input_size: tuple[int, int] | None = None,
    ) -> None:
        if model_path is None:
            model_path = EMOTION_MODEL_PATH
        self.model_path = Path(model_path)
        self.model = EmotionModelCatalog().get("ferplus_onnx")
        self.input_size = input_size or self.model.input_size

        self._validate_model()
        self._load_model()

    def _validate_model(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"No se encontró el modelo de emociones en: {self.model_path}\n"
                "Ejecuta 'python scripts/emotion/download_emotion_model.py' para descargarlo."
            )
        if self.model_path.stat().st_size == 0:
            raise ValueError(f"El modelo está vacío: {self.model_path}")

    def _load_model(self) -> None:
        # Usamos ONNX Runtime con CPU (por defecto)
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        # Obtener nombre de la entrada
        self.input_name = self.session.get_inputs()[0].name
        # Obtener nombre de la salida
        self.output_name = self.session.get_outputs()[0].name

    def predict(self, cropped_face: CroppedFace) -> tuple[str, float]:
        """
        Predice la emoción a partir de un rostro preprocesado.

        Args:
            cropped_face: Objeto CroppedFace con imagen normalizada.

        Returns:
            tuple[str, float]: (emoción, confianza)
        """
        # 1. Verificar que la imagen tenga el tamaño correcto
        img = cropped_face.image
        if img.shape[:2] != self.input_size:
            # Redimensionar si es necesario
            img = cv2.resize(img, self.input_size, interpolation=cv2.INTER_AREA)

        # FER+ conserva la escala de píxeles del preprocesador existente.
        # Preparar entrada float32 NCHW, sin normalización adicional.
        if img.dtype == np.uint8:
            img = img.astype(np.float32)

        # Si es 2D (grises), añadir canal (C=1)
        if len(img.shape) == 2:
            img = np.expand_dims(img, axis=0)  # (1, H, W)
        # Añadir dimensión de batch (N=1)
        input_tensor = np.expand_dims(img, axis=0).astype(np.float32)  # (1, 1, H, W)

        # 3. Inferencia
        outputs = self.session.run(
            [self.output_name],
            {self.input_name: input_tensor},
        )
        logits = outputs[0]  # (1, 8)

        # 4. Obtener probabilidades (softmax)
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        probs = probs[0]  # (8,)

        # 5. Emoción dominante
        top_idx = np.argmax(probs)
        emotion = self.EMOTIONS[top_idx]
        confidence = float(probs[top_idx])

        return emotion, confidence


# Compatibilidad con los imports y scripts anteriores.
EmotionClassifier = FerPlusEmotionClassifier
