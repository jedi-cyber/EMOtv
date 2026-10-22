from collections.abc import Callable
from pathlib import Path
from threading import Lock

from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.application.ports.emotion_classifier import EmotionClassifier
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import FerPlusEmotionClassifier


def create_emotion_classifier(
    model_id: str | None = None,
    *,
    catalog: EmotionModelCatalog | None = None,
    model_path: str | Path | None = None,
    intra_op_threads: int | None = None,
) -> EmotionClassifier:
    """Resuelve el modelo predeterminado sin confundir metadatos con adaptadores.

    intra_op_threads limita los hilos de onnxruntime de esta instancia
    (ONNX_THREADS_PER_SESSION); HardlyHumans usa PyTorch y no lo aplica.
    """
    model = (catalog or EmotionModelCatalog()).get(model_id)
    if model.id == "hardlyhumans_vit":
        from emotv.infrastructure.vision.emotion_classifier.hardlyhumans_classifier import HardlyHumansEmotionClassifier
        return HardlyHumansEmotionClassifier(model_path=model_path)
    if model.id == "hsemotion_enet_b0_8_best_afew":
        from emotv.infrastructure.vision.emotion_classifier.hsemotion_classifier import HSEmotionClassifier
        return HSEmotionClassifier(model_path=model_path, intra_op_threads=intra_op_threads)
    if model.id != "ferplus_onnx":
        raise ValueError(f"No hay adaptador implementado para el modelo: {model.id}")
    return FerPlusEmotionClassifier(model_path=model_path, input_size=model.input_size,
                                    intra_op_threads=intra_op_threads)


class ClassifierCache:
    """Carga cada clasificador una sola vez por proceso y lo reutiliza.

    Los clasificadores no guardan estado entre cuadros (la sesión ONNX admite
    llamadas concurrentes), así que varias sesiones comparten la misma instancia.
    Un fallo de carga no se guarda: la siguiente sesión vuelve a intentarlo.
    """

    def __init__(self, factory: Callable[[str], EmotionClassifier] = create_emotion_classifier) -> None:
        self._factory = factory
        self._classifiers: dict[str, EmotionClassifier] = {}
        self._lock = Lock()

    def get(self, model_id: str) -> EmotionClassifier:
        with self._lock:
            classifier = self._classifiers.get(model_id)
            if classifier is None:
                classifier = self._factory(model_id)
                self._classifiers[model_id] = classifier
            return classifier
