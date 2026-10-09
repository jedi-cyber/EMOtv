from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from emotv.infrastructure.persistence.models import EmotionActivityRecommendationRecord as Record


class PostgresRecommendationRepository:
    """Asociaciones expresión -> actividades en emotion_activity_recommendations."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def activity_ids_for(self, expression_key: str) -> tuple[str, ...]:
        with self._factory() as db:
            return tuple(db.scalars(
                select(Record.activity_id).where(Record.expression_key == expression_key)
                .order_by(Record.priority, Record.activity_id)
            ))

    def list_all(self) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {}
        with self._factory() as db:
            for row in db.scalars(select(Record).order_by(Record.expression_key, Record.priority, Record.activity_id)):
                result.setdefault(row.expression_key, []).append(row.activity_id)
        return {key: tuple(ids) for key, ids in result.items()}

    def replace(self, expression_key: str, activity_ids: Sequence[str]) -> tuple[str, ...]:
        with self._factory.begin() as db:
            db.execute(delete(Record).where(Record.expression_key == expression_key))
            db.add_all(Record(expression_key=expression_key, activity_id=activity_id, priority=index)
                       for index, activity_id in enumerate(activity_ids))
        return tuple(activity_ids)

    def expressions_using(self, activity_id: str) -> tuple[str, ...]:
        with self._factory() as db:
            return tuple(db.scalars(
                select(Record.expression_key).where(Record.activity_id == activity_id)
                .order_by(Record.expression_key)
            ))


class InMemoryRecommendationRepository:
    """Mismo contrato en memoria, para pruebas."""

    def __init__(self, initial: Mapping[str, Sequence[str]] | None = None) -> None:
        self._data = {key: tuple(ids) for key, ids in (initial or {}).items()}

    def activity_ids_for(self, expression_key: str) -> tuple[str, ...]:
        return self._data.get(expression_key, ())

    def list_all(self) -> dict[str, tuple[str, ...]]:
        return {key: ids for key, ids in self._data.items() if ids}

    def replace(self, expression_key: str, activity_ids: Sequence[str]) -> tuple[str, ...]:
        self._data[expression_key] = tuple(activity_ids)
        return self._data[expression_key]

    def expressions_using(self, activity_id: str) -> tuple[str, ...]:
        return tuple(sorted(key for key, ids in self._data.items() if activity_id in ids))
