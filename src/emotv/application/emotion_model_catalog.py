from __future__ import annotations

from collections.abc import Iterable

from emotv.domain.emotion_model import EmotionModel


FERPLUS_LABELS = (
    "neutral",
    "happiness",
    "surprise",
    "sadness",
    "anger",
    "disgust",
    "fear",
    "contempt",
)

DEFAULT_EMOTION_MODELS = (
    EmotionModel(
        id="ferplus_onnx",
        name="FER+ Estándar",
        description="Modelo predeterminado optimizado para ejecución local en CPU.",
        version="1.0",
        input_size=(64, 64),
        emotion_labels=FERPLUS_LABELS,
        is_default=True,
    ),
    EmotionModel(
        id="hardlyhumans_vit",
        name="HardlyHumans ViT (experimental)",
        description="Alternativa facial de ocho clases; requiere dependencias opcionales y benchmark antes de uso web.",
        version="736c91353cf79a0e0c9a86256982be7d9d7c1591",
        input_size=(224, 224),
        emotion_labels=FERPLUS_LABELS,
    ),
)


class EmotionModelCatalog:
    """Catálogo local de modelos faciales que el usuario puede seleccionar."""

    def __init__(
        self,
        models: Iterable[EmotionModel] = DEFAULT_EMOTION_MODELS,
    ) -> None:
        models_by_id: dict[str, EmotionModel] = {}
        default_model: EmotionModel | None = None

        for model in models:
            if not isinstance(model, EmotionModel):
                raise TypeError("Cada elemento debe ser un EmotionModel")
            if model.id in models_by_id:
                raise ValueError(f"Modelo de emociones duplicado: {model.id}")
            if model.is_default:
                if default_model is not None:
                    raise ValueError("Solo puede existir un modelo predeterminado")
                default_model = model
            models_by_id[model.id] = model

        if models_by_id and default_model is None:
            raise ValueError("El catálogo debe tener un modelo predeterminado")

        self._models_by_id = models_by_id
        self._default_model = default_model

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._models_by_id)

    @property
    def default(self) -> EmotionModel:
        if self._default_model is None:
            raise LookupError("El catálogo no tiene un modelo predeterminado")
        return self._default_model

    def get(self, model_id: str | None = None) -> EmotionModel:
        if model_id is None:
            return self.default
        normalized_id = self._normalize_id(model_id)
        try:
            return self._models_by_id[normalized_id]
        except KeyError as error:
            raise KeyError(
                f"Modelo de emociones no encontrado: {normalized_id}"
            ) from error

    def list_all(self) -> tuple[EmotionModel, ...]:
        return tuple(self._models_by_id.values())

    @staticmethod
    def _normalize_id(model_id: str) -> str:
        if not isinstance(model_id, str):
            raise TypeError("model_id debe ser str")
        normalized_id = model_id.strip().lower()
        if not normalized_id:
            raise ValueError("model_id no puede estar vacío")
        return normalized_id
