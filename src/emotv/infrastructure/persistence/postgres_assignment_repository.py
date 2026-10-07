from __future__ import annotations

from datetime import timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.psychologist_assignment import PsychologistAssignment
from emotv.infrastructure.persistence.models import PsychologistAssignmentRecord


class PostgresAssignmentRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def assign(self, assignment: PsychologistAssignment) -> PsychologistAssignment:
        with self._factory.begin() as db:
            row = db.get(PsychologistAssignmentRecord,
                         (assignment.psychologist_user_id, assignment.student_id))
            if row is not None:
                return self._domain(row)
            db.add(PsychologistAssignmentRecord(
                psychologist_user_id=assignment.psychologist_user_id, student_id=assignment.student_id,
                assigned_at=assignment.assigned_at, assigned_by_user_id=assignment.assigned_by_user_id))
        return assignment

    def unassign(self, psychologist_user_id: str, student_id: str) -> bool:
        with self._factory.begin() as db:
            result = db.execute(delete(PsychologistAssignmentRecord).where(
                PsychologistAssignmentRecord.psychologist_user_id == psychologist_user_id,
                PsychologistAssignmentRecord.student_id == student_id))
            return bool(result.rowcount)

    def is_assigned(self, psychologist_user_id: str, student_id: str) -> bool:
        with self._factory() as db:
            return db.get(PsychologistAssignmentRecord, (psychologist_user_id, student_id)) is not None

    def list_by_psychologist(self, psychologist_user_id: str) -> tuple[PsychologistAssignment, ...]:
        with self._factory() as db:
            rows = db.scalars(select(PsychologistAssignmentRecord)
                              .where(PsychologistAssignmentRecord.psychologist_user_id == psychologist_user_id)
                              .order_by(PsychologistAssignmentRecord.assigned_at,
                                        PsychologistAssignmentRecord.student_id)).all()
            return tuple(self._domain(row) for row in rows)

    @staticmethod
    def _domain(row: PsychologistAssignmentRecord) -> PsychologistAssignment:
        assigned_at = row.assigned_at if row.assigned_at.tzinfo else row.assigned_at.replace(tzinfo=timezone.utc)
        return PsychologistAssignment(row.psychologist_user_id, row.student_id, assigned_at,
                                      row.assigned_by_user_id)
