from __future__ import annotations

from collections.abc import Sequence

from emotv.application.activity_catalog import ActivityCatalog
from emotv.application.activity_recommendation_service import MINIMUM_RECOMMENDED_STEPS
from emotv.application.ports.recommendation_repository import RecommendationRepository
from emotv.domain.activity import Activity
from emotv.domain.expression_info import EXPRESSION_KEYS

MAX_ACTIVITIES_PER_EXPRESSION = 20


class RecommendationConfigService:
    """Edición validada de las asociaciones expresión -> actividades."""

    def __init__(self, repository: RecommendationRepository, catalog: ActivityCatalog) -> None:
        self.repository = repository
        self.catalog = catalog

    def list_all(self) -> dict[str, tuple[str, ...]]:
        stored = self.repository.list_all()
        return {key: stored.get(key, ()) for key in EXPRESSION_KEYS}

    def get(self, expression_key: str) -> tuple[str, ...]:
        return self.repository.activity_ids_for(self._require_key(expression_key))

    def replace(self, expression_key: str, activity_ids: Sequence[str]) -> tuple[str, ...]:
        """Valida y guarda; ValueError con el motivo si la lista no es válida."""
        key = self._require_key(expression_key)
        normalized = [item.strip().lower() for item in activity_ids]
        if len(normalized) > MAX_ACTIVITIES_PER_EXPRESSION:
            raise ValueError(f"Una expresión admite como máximo {MAX_ACTIVITIES_PER_EXPRESSION} actividades")
        if len(set(normalized)) != len(normalized):
            raise ValueError("La lista contiene actividades repetidas")
        for activity_id in normalized:
            try:
                activity = self.catalog.get(activity_id)
            except KeyError as error:
                raise ValueError(f"La actividad {activity_id} no existe") from error
            if len(activity.steps) < MINIMUM_RECOMMENDED_STEPS:
                raise ValueError(
                    f"La actividad {activity_id} tiene {len(activity.steps)} paso(s); "
                    f"una recomendación necesita al menos {MINIMUM_RECOMMENDED_STEPS}"
                )
        return self.repository.replace(key, normalized)

    def expressions_blocking_update(self, activity: Activity) -> tuple[str, ...]:
        """Expresiones que quedarían con una recomendación inválida si se guarda ``activity``."""
        if len(activity.steps) >= MINIMUM_RECOMMENDED_STEPS:
            return ()
        return self.repository.expressions_using(activity.id)

    @staticmethod
    def _require_key(expression_key: str) -> str:
        key = expression_key.strip().lower()
        if key not in EXPRESSION_KEYS:
            raise KeyError(expression_key)
        return key
