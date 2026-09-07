from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from emotv.application.activity_catalog import ActivityCatalog
from emotv.domain.activity import Activity


# Asociaciones provisionales para demostrar el flujo técnico del MVP.
# Deben ser revisadas por profesionales de Psicología antes de uso real.
DEFAULT_ACTIVITIES_BY_EMOTION: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "sadness": ("arms_up_5s", "arms_open_5s"),
        "anger": ("arms_open_5s",),
        "neutral": (),
        "happiness": (),
        "surprise": (),
        "disgust": (),
        "fear": (),
        "contempt": (),
    }
)


class ActivityRecommendationService:
    """Recomienda actividades mediante asociaciones locales por emoción."""

    def __init__(
        self,
        catalog: ActivityCatalog | None = None,
        activities_by_emotion: Mapping[str, Sequence[str]] = (
            DEFAULT_ACTIVITIES_BY_EMOTION
        ),
    ) -> None:
        self.catalog = catalog or ActivityCatalog()
        normalized_mapping: dict[str, tuple[str, ...]] = {}

        for emotion, activity_ids in activities_by_emotion.items():
            normalized_emotion = self._normalize_emotion(emotion)
            normalized_ids = tuple(activity_ids)
            for activity_id in normalized_ids:
                self.catalog.get(activity_id)
            normalized_mapping[normalized_emotion] = normalized_ids

        self._activities_by_emotion = MappingProxyType(normalized_mapping)

    @property
    def supported_emotions(self) -> frozenset[str]:
        return frozenset(self._activities_by_emotion)

    def recommend(self, emotion: str) -> Activity | None:
        """Devuelve la primera actividad configurada o ``None``."""

        activities = self.recommend_all(emotion)
        return activities[0] if activities else None

    def recommend_all(self, emotion: str) -> tuple[Activity, ...]:
        """Devuelve todas las actividades asociadas en orden de prioridad."""

        normalized_emotion = self._normalize_emotion(emotion)
        activity_ids = self._activities_by_emotion.get(normalized_emotion, ())
        return tuple(self.catalog.get(activity_id) for activity_id in activity_ids)

    @staticmethod
    def _normalize_emotion(emotion: str) -> str:
        normalized = emotion.strip().lower()
        if not normalized:
            raise ValueError("emotion no puede estar vacía")
        return normalized
