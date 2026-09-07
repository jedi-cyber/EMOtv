from __future__ import annotations

from collections.abc import Iterable

from emotv.domain.activity import Activity
from emotv.domain.posture_id import PostureId


DEFAULT_ACTIVITIES = (
    Activity(
        id="arms_up_5s",
        name="Elevación de brazos",
        description="Levanta ambos brazos y mantenlos extendidos sobre los hombros.",
        required_posture=PostureId.ARMS_UP,
        duration_seconds=5.0,
    ),
    Activity(
        id="arms_open_5s",
        name="Apertura de brazos",
        description="Abre ambos brazos y mantenlos extendidos a la altura de hombros.",
        required_posture=PostureId.ARMS_OPEN,
        duration_seconds=5.0,
    ),
    Activity(
        id="hands_on_hips_5s",
        name="Manos en las caderas",
        description="Coloca ambas manos en las caderas y mantén los codos abiertos.",
        required_posture=PostureId.HANDS_ON_HIPS,
        duration_seconds=5.0,
    ),
)


class ActivityCatalog:
    """Catálogo local y en memoria de actividades disponibles."""

    def __init__(self, activities: Iterable[Activity] = DEFAULT_ACTIVITIES) -> None:
        activities_by_id: dict[str, Activity] = {}
        for activity in activities:
            if activity.id in activities_by_id:
                raise ValueError(f"Actividad duplicada: {activity.id}")
            activities_by_id[activity.id] = activity
        self._activities_by_id = activities_by_id

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._activities_by_id)

    def get(self, activity_id: str) -> Activity:
        try:
            return self._activities_by_id[activity_id]
        except KeyError as error:
            raise KeyError(f"Actividad no encontrada: {activity_id}") from error

    def list_all(self) -> tuple[Activity, ...]:
        return tuple(self._activities_by_id.values())

    def for_posture(self, posture_id: PostureId | str) -> tuple[Activity, ...]:
        normalized_id = PostureId(posture_id)
        return tuple(
            activity
            for activity in self._activities_by_id.values()
            if activity.required_posture is normalized_id
        )
