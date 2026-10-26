"""Persistencia de cuestionarios y de sus respuestas cifradas."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone
import json

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.questionnaire import Question, Questionnaire, QuestionnaireResponse
from emotv.infrastructure.persistence.models import (
    QuestionnaireRecord,
    QuestionnaireResponseRecord,
    SessionRecord,
)
from emotv.shared.security.field_encryption import FieldCipher


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class PostgresQuestionnaireRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    @staticmethod
    def _fill(row: QuestionnaireRecord, item: Questionnaire) -> None:
        row.family_id = item.family_id
        row.version = item.version
        row.owner_user_id = item.owner_user_id
        row.title = item.title
        row.instructions = item.instructions
        row.questions = [question.to_dict() for question in item.questions]
        row.shared_with_group = item.shared_with_group
        row.copied_from_id = item.copied_from_id
        row.created_at = item.created_at
        row.superseded_at = item.superseded_at

    @staticmethod
    def _domain(row: QuestionnaireRecord) -> Questionnaire:
        return Questionnaire(
            id=row.id, family_id=row.family_id, version=row.version, owner_user_id=row.owner_user_id,
            title=row.title, instructions=row.instructions, created_at=_aware(row.created_at),
            questions=tuple(Question.from_dict(item) for item in row.questions),
            shared_with_group=row.shared_with_group, copied_from_id=row.copied_from_id,
            superseded_at=_aware(row.superseded_at))

    def add(self, questionnaire: Questionnaire) -> Questionnaire:
        with self._factory.begin() as db:
            row = QuestionnaireRecord(id=questionnaire.id)
            self._fill(row, questionnaire)
            db.add(row)
        return questionnaire

    def replace(self, questionnaire: Questionnaire) -> Questionnaire:
        with self._factory.begin() as db:
            row = db.get(QuestionnaireRecord, questionnaire.id)
            if row is None:
                raise LookupError(questionnaire.id)
            self._fill(row, questionnaire)
        return questionnaire

    def add_version(self, previous_id: str, superseded_at: datetime, questionnaire: Questionnaire) -> Questionnaire:
        with self._factory.begin() as db:
            previous = db.get(QuestionnaireRecord, previous_id)
            if previous is None:
                raise LookupError(previous_id)
            previous.superseded_at = superseded_at
            # La plantilla compartida pasa a la versión nueva.
            previous.shared_with_group = False
            row = QuestionnaireRecord(id=questionnaire.id)
            self._fill(row, replace(questionnaire, superseded_at=None))
            db.add(row)
        return questionnaire

    def get(self, questionnaire_id: str) -> Questionnaire | None:
        with self._factory() as db:
            row = db.get(QuestionnaireRecord, questionnaire_id)
            return None if row is None else self._domain(row)

    def current_of_family(self, family_id: str) -> Questionnaire | None:
        with self._factory() as db:
            row = db.scalars(select(QuestionnaireRecord).where(QuestionnaireRecord.family_id == family_id,
                                                               QuestionnaireRecord.superseded_at.is_(None))).first()
            return None if row is None else self._domain(row)

    def list_current(self, owner_ids: Iterable[str], shared_owner_ids: Iterable[str] = ()) -> tuple[Questionnaire, ...]:
        owners, sharing = tuple(owner_ids), tuple(shared_owner_ids)
        conditions = []
        if owners:
            conditions.append(QuestionnaireRecord.owner_user_id.in_(owners))
        if sharing:
            conditions.append(and_(QuestionnaireRecord.owner_user_id.in_(sharing),
                                   QuestionnaireRecord.shared_with_group.is_(True)))
        if not conditions:
            return ()
        with self._factory() as db:
            rows = db.scalars(select(QuestionnaireRecord).where(or_(*conditions),
                                                                QuestionnaireRecord.superseded_at.is_(None))
                              .order_by(QuestionnaireRecord.created_at, QuestionnaireRecord.id)).all()
            return tuple(self._domain(row) for row in rows)

    def is_used(self, questionnaire_id: str) -> bool:
        with self._factory() as db:
            sessions = db.scalar(select(func.count()).select_from(SessionRecord).where(or_(
                SessionRecord.pre_questionnaire_id == questionnaire_id,
                SessionRecord.post_questionnaire_id == questionnaire_id)))
            responses = db.scalar(select(func.count()).select_from(QuestionnaireResponseRecord)
                                  .where(QuestionnaireResponseRecord.questionnaire_id == questionnaire_id))
            return bool(sessions or responses)


class PostgresQuestionnaireResponseRepository:
    """Las respuestas se cifran como JSON antes de guardarse y se descifran al leer."""

    def __init__(self, factory: sessionmaker[Session], cipher: FieldCipher) -> None:
        self._factory = factory
        self._cipher = cipher

    def _domain(self, row: QuestionnaireResponseRecord) -> QuestionnaireResponse:
        return QuestionnaireResponse(
            id=row.id, session_id=row.session_id, questionnaire_id=row.questionnaire_id, moment=row.moment,
            answers=json.loads(self._cipher.decrypt(row.answers_encrypted) or "{}"), entry_mode=row.entry_mode,
            recorded_by_user_id=row.recorded_by_user_id, submitted_at=_aware(row.submitted_at))

    def add(self, response: QuestionnaireResponse) -> QuestionnaireResponse:
        with self._factory.begin() as db:
            db.add(QuestionnaireResponseRecord(
                id=response.id, session_id=response.session_id, questionnaire_id=response.questionnaire_id,
                moment=response.moment.value,
                answers_encrypted=self._cipher.encrypt(json.dumps(response.answers, ensure_ascii=False)),
                entry_mode=response.entry_mode.value, recorded_by_user_id=response.recorded_by_user_id,
                submitted_at=response.submitted_at))
        return response

    def get(self, session_id: str, moment: str) -> QuestionnaireResponse | None:
        with self._factory() as db:
            row = db.scalars(select(QuestionnaireResponseRecord).where(
                QuestionnaireResponseRecord.session_id == session_id,
                QuestionnaireResponseRecord.moment == moment)).first()
            return None if row is None else self._domain(row)

    def list_for_session(self, session_id: str) -> tuple[QuestionnaireResponse, ...]:
        with self._factory() as db:
            rows = db.scalars(select(QuestionnaireResponseRecord)
                              .where(QuestionnaireResponseRecord.session_id == session_id)
                              .order_by(QuestionnaireResponseRecord.submitted_at)).all()
            return tuple(self._domain(row) for row in rows)
