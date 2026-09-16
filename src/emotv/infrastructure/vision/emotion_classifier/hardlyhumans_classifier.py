from pathlib import Path

import cv2
import numpy as np

from emotv.application.emotion_model_catalog import EmotionModelCatalog, FERPLUS_LABELS
from emotv.config import HARDLYHUMANS_MODEL_DIR
from emotv.domain.cropped_face import CroppedFace


LABEL_ALIASES = {"angry": "anger", "happy": "happiness", "sad": "sadness"}


def canonical_labels(id2label: dict) -> tuple[str, ...]:
    if len(id2label) != 8:
        raise ValueError("El modelo debe contener ocho clases")
    labels = []
    for index in range(8):
        label = str(id2label.get(index, id2label.get(str(index), ""))).strip().lower()
        labels.append(LABEL_ALIASES.get(label, label))
    if set(labels) != set(FERPLUS_LABELS):
        raise ValueError("Las clases del modelo no son compatibles con EMOtv")
    return tuple(labels)


class HardlyHumansEmotionClassifier:
    """ViT local en CPU; sin código remoto, pickle ni descargas durante inferencia."""
    face_preprocessor_options = dict(target_size=None, grayscale=False, normalize=False)

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = Path(model_path) if model_path is not None else HARDLYHUMANS_MODEL_DIR
        for filename in ("config.json", "preprocessor_config.json", "model.safetensors"):
            if not (self.model_path / filename).is_file():
                raise FileNotFoundError("Modelo ViT no instalado. Ejecuta python scripts/emotion/download_hardlyhumans_model.py")
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForImageClassification
        except ImportError as error:
            raise RuntimeError('Instala las dependencias opcionales: python -m pip install -e ".[emotion-vit]"') from error
        self._torch = torch
        self.model = EmotionModelCatalog().get("hardlyhumans_vit")
        self.processor = AutoImageProcessor.from_pretrained(str(self.model_path), local_files_only=True, trust_remote_code=False, use_fast=False)
        self.network = AutoModelForImageClassification.from_pretrained(str(self.model_path), local_files_only=True, trust_remote_code=False, use_safetensors=True).to("cpu").eval()
        self.labels = canonical_labels(self.network.config.id2label)

    def predict(self, cropped_face: CroppedFace) -> tuple[str, float]:
        image = cropped_face.image
        if image is None or image.size == 0 or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("ViT requiere un recorte BGR uint8 sin normalizar, con tres canales")
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        inputs = self.processor(images=rgb, return_tensors="pt")
        with self._torch.inference_mode():
            logits = self.network(**inputs).logits
            if tuple(logits.shape) != (1, 8) or not self._torch.isfinite(logits).all().item():
                raise ValueError("Salida ViT inválida")
            probabilities = self._torch.softmax(logits, dim=-1)[0]
            index = int(probabilities.argmax().item())
            return self.labels[index], float(probabilities[index].item())
