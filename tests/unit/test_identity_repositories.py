from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine

from emotv.application.ports import ConsentRepository, StudentRepository, UserRepository
from emotv.domain import ConsentRecord, Role, Student, User
from emotv.infrastructure.persistence import (
    Base, PostgresConsentRepository, PostgresStudentRepository,
    PostgresUserRepository, create_session_factory,
)


class IdentityRepositoriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        factory = create_session_factory(self.engine)
        self.users = PostgresUserRepository(factory)
        self.students = PostgresStudentRepository(factory)
        self.consents = PostgresConsentRepository(factory)
        self.now = datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.user = User("user-1", "student@example.com", "argon-hash",
                         Role.STUDENT, self.now)
        self.student = Student("student-1", self.user.id, "2026-001")

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_implement_contracts(self) -> None:
        self.assertIsInstance(self.users, UserRepository)
        self.assertIsInstance(self.students, StudentRepository)
        self.assertIsInstance(self.consents, ConsentRepository)

    def test_user_crud_queries(self) -> None:
        self.users.save(self.user)
        self.assertEqual(self.users.get_by_id("user-1"), self.user)
        self.assertEqual(self.users.get_by_email("STUDENT@example.com"), self.user)
        self.assertEqual(self.users.list_all(), (self.user,))

    def test_student_crud_queries(self) -> None:
        self.users.save(self.user)
        self.students.save(self.student)
        self.assertEqual(self.students.get_by_id("student-1"), self.student)
        self.assertEqual(self.students.get_by_user_id("user-1"), self.student)
        self.assertEqual(self.students.get_by_code("2026-001"), self.student)

    def test_consent_history_active_and_revoked(self) -> None:
        self.users.save(self.user)
        self.students.save(self.student)
        consent = ConsentRecord("consent-1", self.student.id, "privacy-v1", self.now)
        self.consents.save(consent)
        self.assertEqual(self.consents.get_active_by_student(self.student.id), consent)
        revoked = ConsentRecord(consent.id, consent.student_id, consent.policy_version,
                                consent.granted_at, self.now + timedelta(seconds=1))
        self.consents.save(revoked)
        self.assertIsNone(self.consents.get_active_by_student(self.student.id))
        self.assertEqual(self.consents.list_by_student(self.student.id), (revoked,))


if __name__ == "__main__":
    unittest.main()
