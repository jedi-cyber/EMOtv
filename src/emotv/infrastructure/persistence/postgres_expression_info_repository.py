from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.expression_info import TEXT_FIELDS, ExpressionInfo
from emotv.infrastructure.persistence.models import ExpressionInfoRecord

_FIELDS = ("label_es", *TEXT_FIELDS, "reviewed_by_user_id", "reviewed_at", "updated_at")


class PostgresExpressionInfoRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def list_all(self) -> tuple[ExpressionInfo, ...]:
        with self._factory() as db:
            return tuple(self._domain(row) for row in db.scalars(select(ExpressionInfoRecord)).all())

    def get(self, expression_key: str) -> ExpressionInfo | None:
        with self._factory() as db:
            row = db.get(ExpressionInfoRecord, expression_key)
            return None if row is None else self._domain(row)

    def save(self, info: ExpressionInfo) -> ExpressionInfo:
        with self._factory.begin() as db:
            row = db.get(ExpressionInfoRecord, info.expression_key)
            if row is None:
                row = ExpressionInfoRecord(expression_key=info.expression_key)
                db.add(row)
            for field in _FIELDS:
                setattr(row, field, getattr(info, field))
            row.review_status = info.review_status.value
        return info

    @staticmethod
    def _aware(value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @classmethod
    def _domain(cls, row: ExpressionInfoRecord) -> ExpressionInfo:
        return ExpressionInfo(
            expression_key=row.expression_key,
            label_es=row.label_es,
            what_it_is=row.what_it_is,
            why_it_occurs=row.why_it_occurs,
            facial_cues=row.facial_cues,
            practice_tip=row.practice_tip,
            limitation_note=row.limitation_note,
            review_status=row.review_status,
            reviewed_by_user_id=row.reviewed_by_user_id,
            reviewed_at=cls._aware(row.reviewed_at),
            updated_at=cls._aware(row.updated_at),
        )


class InMemoryExpressionInfoRepository:
    def __init__(self, items: tuple[ExpressionInfo, ...] = ()) -> None:
        self._items = {item.expression_key: item for item in items}

    def list_all(self) -> tuple[ExpressionInfo, ...]:
        return tuple(self._items.values())

    def get(self, expression_key: str) -> ExpressionInfo | None:
        return self._items.get(expression_key)

    def save(self, info: ExpressionInfo) -> ExpressionInfo:
        self._items[info.expression_key] = info
        return info
