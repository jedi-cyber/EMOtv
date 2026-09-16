from pathlib import Path

from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.application.ports.emotion_classifier import EmotionClassifier
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import FerPlusEmotionClassifier


def create_emotion_classifier(
    model_id: str | None = None,
    *,
    catalog: EmotionModelCatalog | None = None,
    model_path: str | Path | None = None,
) -> EmotionClassifier:
    """Resuelve el modelo predeterminado sin confundir metadatos con adaptadores."""
    model = (catalog or EmotionModelCatalog()).get(model_id)
    if model.id == "hardlyhumans_vit":
        from emotv.infrastructure.vision.emotion_classifier.hardlyhumans_classifier import HardlyHumansEmotionClassifier
        return HardlyHumansEmotionClassifier(model_path=model_path)
    if model.id != "ferplus_onnx":
        raise ValueError(f"No hay adaptador implementado para el modelo: {model.id}")
    return FerPlusEmotionClassifier(model_path=model_path, input_size=model.input_size)
