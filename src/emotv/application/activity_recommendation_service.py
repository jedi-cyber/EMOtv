from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
import random
from threading import Lock

from emotv.application.activity_catalog import ActivityCatalog
from emotv.domain.activity import Activity


# Asociaciones provisionales para demostrar el flujo técnico del MVP.
# Deben ser revisadas por profesionales de Psicología antes de uso real.
DEFAULT_ACTIVITIES_BY_EMOTION: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "sadness": ("morning_mobility", "open_and_reach"),
        "anger": ("upper_body_flow", "balanced_postures"),
        "neutral": ("balanced_postures", "morning_mobility", "upper_body_flow"),
        "happiness": ("full_body_flow", "open_and_reach", "gentle_squat_flow"),
        "surprise": ("open_and_reach", "upper_body_flow"),
        "disgust": ("balanced_postures", "morning_mobility"),
        "fear": ("morning_mobility", "balanced_postures"),
        "contempt": ("upper_body_flow", "open_and_reach"),
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
        minimum_steps: int = 2,
    ) -> None:
        if isinstance(minimum_steps, bool) or minimum_steps < 1:
            raise ValueError("minimum_steps debe ser un entero mayor o igual que 1")
        self.catalog = catalog or ActivityCatalog()
        normalized_mapping: dict[str, tuple[str, ...]] = {}

        for emotion, activity_ids in activities_by_emotion.items():
            normalized_emotion = self._normalize_emotion(emotion)
            normalized_ids = tuple(activity_ids)
            for activity_id in normalized_ids:
                activity = self.catalog.get(activity_id)
                if len(activity.steps) < minimum_steps:
                    raise ValueError(
                        f"La actividad recomendada {activity_id} debe tener al menos "
                        f"{minimum_steps} steps"
                    )
            normalized_mapping[normalized_emotion] = normalized_ids

        self._activities_by_emotion = MappingProxyType(normalized_mapping)
        self._last_by_emotion: dict[str, str] = {}
        self._lock = Lock()

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

    def recommend_varied(self, emotion: str, *, exclude_ids: Sequence[str] = ()) -> Activity | None:
        """Elige entre candidatos configurados, evitando la última elección si es posible."""
        candidates = self.recommend_all(emotion)
        if not candidates:
            return None
        key = self._normalize_emotion(emotion)
        with self._lock:
            preferred = [item for item in candidates if item.id not in exclude_ids
                         and item.id != self._last_by_emotion.get(key)]
            selected = random.SystemRandom().choice(preferred or [item for item in candidates if item.id not in exclude_ids] or list(candidates))
            self._last_by_emotion[key] = selected.id
            return selected

    @staticmethod
    def _normalize_emotion(emotion: str) -> str:
        normalized = emotion.strip().lower()
        if not normalized:
            raise ValueError("emotion no puede estar vacía")
        return normalized
