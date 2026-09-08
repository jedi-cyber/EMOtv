from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.consent import ConsentRecord
from emotv.infrastructure.persistence.models import ConsentRecordModel
from emotv.infrastructure.persistence.postgres_user_repository import _text


class PostgresConsentRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def save(self, consent: ConsentRecord) -> ConsentRecord:
        if not isinstance(consent, ConsentRecord):
            raise TypeError("consent debe ser ConsentRecord")
        with self._factory.begin() as db:
            row = db.get(ConsentRecordModel, consent.id)
            if row is None:
                db.add(ConsentRecordModel(id=consent.id, student_id=consent.student_id,
                    policy_version=consent.policy_version, granted_at=consent.granted_at,
                    revoked_at=consent.revoked_at))
            else:
                row.student_id, row.policy_version = consent.student_id, consent.policy_version
                row.granted_at, row.revoked_at = consent.granted_at, consent.revoked_at
        return consent

    def get_by_id(self, consent_id: str) -> ConsentRecord | None:
        with self._factory() as db:
            row = db.get(ConsentRecordModel, _text(consent_id, "consent_id"))
            return None if row is None else self._domain(row)

    def list_by_student(self, student_id: str) -> tuple[ConsentRecord, ...]:
        statement = select(ConsentRecordModel).where(
            ConsentRecordModel.student_id == _text(student_id, "student_id")
        ).order_by(ConsentRecordModel.granted_at.desc(), ConsentRecordModel.id)
        with self._factory() as db:
            return tuple(self._domain(row) for row in db.scalars(statement).all())

    def get_active_by_student(self, student_id: str) -> ConsentRecord | None:
        statement = select(ConsentRecordModel).where(
            ConsentRecordModel.student_id == _text(student_id, "student_id"),
            ConsentRecordModel.revoked_at.is_(None),
        ).order_by(ConsentRecordModel.granted_at.desc()).limit(1)
        with self._factory() as db:
            row = db.scalar(statement)
            return None if row is None else self._domain(row)

    @staticmethod
    def _domain(row: ConsentRecordModel) -> ConsentRecord:
        aware = lambda value: value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return ConsentRecord(row.id, row.student_id, row.policy_version,
                             aware(row.granted_at), aware(row.revoked_at) if row.revoked_at else None)
