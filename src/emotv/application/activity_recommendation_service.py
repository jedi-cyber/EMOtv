from __future__ import annotations

import logging
import random
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from emotv.application.activity_catalog import ActivityCatalog
from emotv.application.ports.recommendation_repository import RecommendationSource
from emotv.domain.activity import Activity

logger = logging.getLogger(__name__)

MINIMUM_RECOMMENDED_STEPS = 2

# Asociaciones por defecto solo para el flujo local (scripts de diagnóstico y
# pruebas). La web las lee de PostgreSQL (emotion_activity_recommendations),
# donde administración las edita sin cambiar código; la migración 20261009_13
# las cargó como valores iniciales. Deben revisarlas profesionales de Psicología.
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


class StaticRecommendations:
    """Fuente de asociaciones fija, para el flujo local sin base de datos."""

    def __init__(self, activities_by_emotion: Mapping[str, Sequence[str]]) -> None:
        self._mapping = MappingProxyType({
            _normalize(emotion): tuple(ids) for emotion, ids in activities_by_emotion.items()
        })

    def activity_ids_for(self, expression_key: str) -> tuple[str, ...]:
        return self._mapping.get(_normalize(expression_key), ())


class ActivityRecommendationService:
    """Recomienda actividades según asociaciones configurables por expresión.

    No guarda estado entre llamadas: lee las asociaciones cada vez, así que un
    cambio de administración se aplica en la siguiente recomendación y puede
    compartirse entre conexiones y procesos. Los datos de configuración
    inválidos (actividad inexistente o con menos de dos pasos) se descartan
    con un aviso en el log; nunca interrumpen el análisis.
    """

    def __init__(
        self,
        catalog: ActivityCatalog | None = None,
        activities_by_emotion: Mapping[str, Sequence[str]] | None = None,
        minimum_steps: int = MINIMUM_RECOMMENDED_STEPS,
        *,
        source: RecommendationSource | None = None,
    ) -> None:
        if isinstance(minimum_steps, bool) or minimum_steps < 1:
            raise ValueError("minimum_steps debe ser un entero mayor o igual que 1")
        if source is not None and activities_by_emotion is not None:
            raise ValueError("indica source o activities_by_emotion, no ambos")
        self.catalog = catalog or ActivityCatalog()
        self.source = source or StaticRecommendations(
            DEFAULT_ACTIVITIES_BY_EMOTION if activities_by_emotion is None else activities_by_emotion
        )
        self.minimum_steps = minimum_steps

    def recommend(self, emotion: str) -> Activity | None:
        """Devuelve la primera actividad válida configurada o ``None``."""

        activities = self.recommend_all(emotion)
        return activities[0] if activities else None

    def recommend_all(self, emotion: str) -> tuple[Activity, ...]:
        """Devuelve las actividades válidas asociadas, en orden de prioridad."""

        key = _normalize(emotion)
        valid: list[Activity] = []
        for activity_id in self.source.activity_ids_for(key):
            try:
                activity = self.catalog.get(activity_id)
            except KeyError:
                logger.warning(
                    "Recomendación omitida: la actividad %s asociada a %s no existe", activity_id, key,
                )
                continue
            if len(activity.steps) < self.minimum_steps:
                logger.warning(
                    "Recomendación omitida: la actividad %s asociada a %s tiene %d paso(s); "
                    "se requieren al menos %d", activity_id, key, len(activity.steps), self.minimum_steps,
                )
                continue
            valid.append(activity)
        return tuple(valid)

    def recommend_varied(self, emotion: str, *, exclude_ids: Sequence[str] = ()) -> Activity | None:
        """Elige al azar entre los candidatos válidos, evitando ``exclude_ids`` si es posible.

        La variación la aporta el llamador (por ejemplo, la última actividad del
        historial del estudiante), no un estado en memoria del proceso.
        """
        candidates = self.recommend_all(emotion)
        if not candidates:
            return None
        preferred = [item for item in candidates if item.id not in exclude_ids]
        return random.SystemRandom().choice(preferred or list(candidates))


def _normalize(emotion: str) -> str:
    normalized = emotion.strip().lower()
    if not normalized:
        raise ValueError("emotion no puede estar vacía")
    return normalized
