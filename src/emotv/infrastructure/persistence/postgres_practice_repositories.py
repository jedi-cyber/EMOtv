"""Persistencia de estímulos y protocolos."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.notice import UserNotice
from emotv.domain.protocol import Protocol, ProtocolStep
from emotv.domain.stimulus import Stimulus, StimulusScope
from emotv.infrastructure.persistence.models import (
    ExpressionCaptureRecord,
    ProtocolRecord,
    ProtocolStepRecord,
    SessionRecord,
    StimulusRecord,
    UserNoticeRecord,
    VerbalResponseRecord,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _enum_value(value):
    return getattr(value, "value", value)


class PostgresStimulusRepository:
    """La imagen se lee solo con get_image; los listados no la cargan."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    @staticmethod
    def _fill(row: StimulusRecord, item: Stimulus) -> None:
        row.title = item.title
        row.kind = _enum_value(item.kind)
        row.category = item.category
        row.expected_expression = item.expected_expression
        row.intensity = _enum_value(item.intensity)
        row.min_age = item.min_age
        row.origin = item.origin
        row.license = item.license
        row.scope = _enum_value(item.scope)
        row.owner_user_id = item.owner_user_id
        row.content_type = item.content_type
        row.created_at = item.created_at
        row.approved_at = item.approved_at
        row.approved_by_user_id = item.approved_by_user_id
        row.active = item.active
        row.possible_person = item.possible_person
        row.upload_batch_id = item.upload_batch_id
        row.expiry_notified_at = item.expiry_notified_at
        row.deleted_at = item.deleted_at

    @staticmethod
    def _domain(row) -> Stimulus:
        return Stimulus(
            id=row.id, title=row.title, kind=row.kind, category=row.category,
            expected_expression=row.expected_expression, intensity=row.intensity, min_age=row.min_age,
            origin=row.origin, license=row.license, scope=row.scope, owner_user_id=row.owner_user_id,
            content_type=row.content_type, created_at=_aware(row.created_at), approved_at=_aware(row.approved_at),
            approved_by_user_id=row.approved_by_user_id, active=row.active,
            possible_person=bool(row.possible_person), upload_batch_id=row.upload_batch_id,
            expiry_notified_at=_aware(row.expiry_notified_at), deleted_at=_aware(row.deleted_at))

    _COLUMNS = tuple(column for column in StimulusRecord.__table__.columns if column.name != "image")

    def add(self, stimulus: Stimulus, image: bytes) -> Stimulus:
        with self._factory.begin() as db:
            row = StimulusRecord(id=stimulus.id, image=image)
            self._fill(row, stimulus)
            db.add(row)
        return stimulus

    def save(self, stimulus: Stimulus) -> Stimulus:
        with self._factory.begin() as db:
            row = db.get(StimulusRecord, stimulus.id)
            if row is None:
                raise LookupError(stimulus.id)
            self._fill(row, stimulus)
        return stimulus

    def get(self, stimulus_id: str) -> Stimulus | None:
        with self._factory() as db:
            row = db.execute(select(*self._COLUMNS).where(StimulusRecord.id == stimulus_id)).first()
            return None if row is None else self._domain(row)

    def get_image(self, stimulus_id: str) -> tuple[str, bytes] | None:
        with self._factory() as db:
            row = db.execute(select(StimulusRecord.content_type, StimulusRecord.image)
                             .where(StimulusRecord.id == stimulus_id, StimulusRecord.deleted_at.is_(None))).first()
            return None if row is None else (row.content_type, bytes(row.image))

    def _list(self, condition) -> tuple[Stimulus, ...]:
        with self._factory() as db:
            rows = db.execute(select(*self._COLUMNS).where(condition, StimulusRecord.deleted_at.is_(None))
                              .order_by(StimulusRecord.created_at, StimulusRecord.id)).all()
            return tuple(self._domain(row) for row in rows)

    def list_visible(self, group_owner_ids: Iterable[str],
                     user_image_owner_id: str | None = None) -> tuple[Stimulus, ...]:
        owners = tuple(group_owner_ids)
        condition = StimulusRecord.scope == StimulusScope.INSTITUTION.value
        if owners:
            condition = or_(condition, (StimulusRecord.scope == StimulusScope.GROUP.value)
                            & StimulusRecord.owner_user_id.in_(owners))
        if user_image_owner_id:
            condition = or_(condition, (StimulusRecord.scope == StimulusScope.USER.value)
                            & (StimulusRecord.owner_user_id == user_image_owner_id)
                            & StimulusRecord.approved_at.is_not(None))
        return self._list(condition)

    def list_user_images(self, owner_ids: Iterable[str]) -> tuple[Stimulus, ...]:
        owners = tuple(owner_ids)
        if not owners:
            return ()
        return self._list((StimulusRecord.scope == StimulusScope.USER.value)
                          & StimulusRecord.owner_user_id.in_(owners))

    def list_pending(self) -> tuple[Stimulus, ...]:
        return self._list((StimulusRecord.scope == StimulusScope.USER.value) & StimulusRecord.approved_at.is_(None))

    def remove(self, stimulus_id: str, deleted_at: datetime) -> None:
        with self._factory.begin() as db:
            row = db.get(StimulusRecord, stimulus_id)
            if row is None:
                return
            referenced = any(db.scalar(select(func.count()).select_from(table).where(column == stimulus_id))
                             for table, column in ((ProtocolStepRecord, ProtocolStepRecord.stimulus_id),
                                                   (ExpressionCaptureRecord, ExpressionCaptureRecord.stimulus_id),
                                                   (VerbalResponseRecord, VerbalResponseRecord.stimulus_id)))
            if not referenced:
                db.delete(row)
                return
            # Una sesión o un protocolo la nombran: se borra el archivo y el
            # registro queda solo como referencia, sin imagen.
            row.image = b""
            row.active = False
            row.deleted_at = deleted_at


class PostgresProtocolRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    @staticmethod
    def _fill(db: Session, row: ProtocolRecord, item: Protocol) -> None:
        row.family_id = item.family_id
        row.version = item.version
        row.owner_user_id = item.owner_user_id
        row.name = item.name
        row.description = item.description
        row.for_children = item.for_children
        row.pre_questionnaire_id = item.pre_questionnaire_id
        row.post_questionnaire_id = item.post_questionnaire_id
        row.created_at = item.created_at
        row.approved_at = item.approved_at
        row.approved_by_user_id = item.approved_by_user_id
        row.superseded_at = item.superseded_at
        row.kind = item.kind.value
        db.add(row)
        db.flush()  # la versión existe antes que sus pasos
        db.execute(delete(ProtocolStepRecord).where(ProtocolStepRecord.protocol_id == item.id))
        db.add_all(ProtocolStepRecord(
            id=str(uuid4()), protocol_id=item.id, position=position, stimulus_id=step.stimulus_id,
            exposure_seconds=step.exposure_seconds, capture_after_seconds=step.capture_after_seconds,
            record_verbal_response=step.record_verbal_response,
            shown_before_analyzer=step.shown_before_analyzer, kind=step.kind.value,
            target_expression=step.target_expression, hold_seconds=step.hold_seconds)
            for position, step in enumerate(item.steps))

    @staticmethod
    def _domain(db: Session, row: ProtocolRecord) -> Protocol:
        steps = db.scalars(select(ProtocolStepRecord).where(ProtocolStepRecord.protocol_id == row.id)
                           .order_by(ProtocolStepRecord.position)).all()
        return Protocol(
            id=row.id, family_id=row.family_id, version=row.version, owner_user_id=row.owner_user_id,
            name=row.name, description=row.description, for_children=row.for_children,
            created_at=_aware(row.created_at), pre_questionnaire_id=row.pre_questionnaire_id,
            post_questionnaire_id=row.post_questionnaire_id,
            approved_at=_aware(row.approved_at), approved_by_user_id=row.approved_by_user_id,
            superseded_at=_aware(row.superseded_at), kind=row.kind or "practice",
            steps=tuple(ProtocolStep(step.stimulus_id, step.exposure_seconds, step.capture_after_seconds,
                                     step.record_verbal_response, step.shown_before_analyzer,
                                     kind=step.kind or "stimulus", target_expression=step.target_expression,
                                     hold_seconds=step.hold_seconds) for step in steps))

    def add(self, protocol: Protocol) -> Protocol:
        with self._factory.begin() as db:
            row = ProtocolRecord(id=protocol.id)
            self._fill(db, row, protocol)
        return protocol

    def replace(self, protocol: Protocol) -> Protocol:
        with self._factory.begin() as db:
            row = db.get(ProtocolRecord, protocol.id)
            if row is None:
                raise LookupError(protocol.id)
            self._fill(db, row, protocol)
        return protocol

    def add_version(self, previous_id: str, superseded_at: datetime, protocol: Protocol) -> Protocol:
        with self._factory.begin() as db:
            previous = db.get(ProtocolRecord, previous_id)
            if previous is None:
                raise LookupError(previous_id)
            previous.superseded_at = superseded_at
            row = ProtocolRecord(id=protocol.id)
            self._fill(db, row, replace(protocol, superseded_at=None))
        return protocol

    def get(self, protocol_id: str) -> Protocol | None:
        with self._factory() as db:
            row = db.get(ProtocolRecord, protocol_id)
            return None if row is None else self._domain(db, row)

    def list_current(self, owner_ids: Iterable[str]) -> tuple[Protocol, ...]:
        owners = tuple(owner_ids)
        if not owners:
            return ()
        with self._factory() as db:
            rows = db.scalars(select(ProtocolRecord).where(ProtocolRecord.owner_user_id.in_(owners),
                                                           ProtocolRecord.superseded_at.is_(None))
                              .order_by(ProtocolRecord.created_at, ProtocolRecord.id)).all()
            return tuple(self._domain(db, row) for row in rows)

    def is_used(self, protocol_id: str) -> bool:
        with self._factory() as db:
            return db.scalar(select(func.count()).select_from(SessionRecord)
                             .where(SessionRecord.protocol_id == protocol_id)) > 0

    def list_current_using(self, stimulus_id: str) -> tuple[Protocol, ...]:
        with self._factory() as db:
            using = select(ProtocolStepRecord.protocol_id).where(ProtocolStepRecord.stimulus_id == stimulus_id)
            rows = db.scalars(select(ProtocolRecord).where(ProtocolRecord.id.in_(using),
                                                           ProtocolRecord.superseded_at.is_(None))
                              .order_by(ProtocolRecord.created_at, ProtocolRecord.id)).all()
            return tuple(self._domain(db, row) for row in rows)


class PostgresNoticeRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def add(self, notice: UserNotice) -> UserNotice:
        with self._factory.begin() as db:
            db.add(UserNoticeRecord(id=notice.id, user_id=notice.user_id, message=notice.message,
                                    created_at=notice.created_at, read_at=notice.read_at))
        return notice

    def list_unread(self, user_id: str) -> tuple[UserNotice, ...]:
        with self._factory() as db:
            rows = db.scalars(select(UserNoticeRecord).where(UserNoticeRecord.user_id == user_id,
                                                             UserNoticeRecord.read_at.is_(None))
                              .order_by(UserNoticeRecord.created_at, UserNoticeRecord.id)).all()
            return tuple(UserNotice(id=row.id, user_id=row.user_id, message=row.message,
                                    created_at=_aware(row.created_at)) for row in rows)

    def mark_read(self, notice_id: str, user_id: str, read_at: datetime) -> bool:
        with self._factory.begin() as db:
            row = db.get(UserNoticeRecord, notice_id)
            if row is None or row.user_id != user_id:
                return False
            if row.read_at is None:
                row.read_at = read_at
            return True
