from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.user import Student
from emotv.infrastructure.persistence.models import StudentRecord
from emotv.infrastructure.persistence.postgres_user_repository import _text


class PostgresStudentRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def save(self, student: Student) -> Student:
        if not isinstance(student, Student):
            raise TypeError("student debe ser Student")
        with self._factory.begin() as db:
            row = db.get(StudentRecord, student.id)
            if row is None:
                db.add(StudentRecord(id=student.id, user_id=student.user_id,
                                     student_code=student.student_code))
            else:
                row.user_id, row.student_code = student.user_id, student.student_code
        return student

    def get_by_id(self, student_id: str) -> Student | None:
        return self._one(StudentRecord.id, _text(student_id, "student_id"))

    def get_by_user_id(self, user_id: str) -> Student | None:
        return self._one(StudentRecord.user_id, _text(user_id, "user_id"))

    def get_by_code(self, student_code: str) -> Student | None:
        return self._one(StudentRecord.student_code, _text(student_code, "student_code"))

    def _one(self, column: object, value: str) -> Student | None:
        with self._factory() as db:
            row = db.scalar(select(StudentRecord).where(column == value))
            return None if row is None else Student(row.id, row.user_id, row.student_code)

    def list_all(self) -> tuple[Student, ...]:
        with self._factory() as db:
            rows = db.scalars(select(StudentRecord).order_by(StudentRecord.student_code)).all()
            return tuple(Student(row.id, row.user_id, row.student_code) for row in rows)
