from __future__ import annotations

import unittest
from datetime import datetime, timezone

from emotv.application import IdentityRegistrationService
from emotv.domain import ConsentRecord, Role, Student, User


class MemoryUsers:
    def __init__(self) -> None: self.items: dict[str, User] = {}
    def save(self, value: User) -> User: self.items[value.id] = value; return value
    def get_by_id(self, value: str) -> User | None: return self.items.get(value)
    def get_by_email(self, value: str) -> User | None:
        return next((x for x in self.items.values() if x.email == value), None)
    def list_all(self) -> tuple[User, ...]: return tuple(self.items.values())


class MemoryStudents:
    def __init__(self) -> None: self.items: dict[str, Student] = {}
    def save(self, value: Student) -> Student: self.items[value.id] = value; return value
    def get_by_id(self, value: str) -> Student | None: return self.items.get(value)
    def get_by_user_id(self, value: str) -> Student | None:
        return next((x for x in self.items.values() if x.user_id == value), None)
    def get_by_code(self, value: str) -> Student | None:
        return next((x for x in self.items.values() if x.student_code == value), None)
    def list_all(self) -> tuple[Student, ...]: return tuple(self.items.values())


class MemoryConsents:
    def __init__(self) -> None: self.items: dict[str, ConsentRecord] = {}
    def save(self, value: ConsentRecord) -> ConsentRecord: self.items[value.id] = value; return value
    def get_by_id(self, value: str) -> ConsentRecord | None: return self.items.get(value)
    def list_by_student(self, value: str) -> tuple[ConsentRecord, ...]:
        return tuple(x for x in self.items.values() if x.student_id == value)
    def get_active_by_student(self, value: str) -> ConsentRecord | None:
        return next((x for x in self.items.values() if x.student_id == value and x.is_active), None)


class FakeHasher:
    def hash_password(self, password: str) -> str: return f"hashed:{password}"


class IdentityRegistrationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.users, self.students, self.consents = MemoryUsers(), MemoryStudents(), MemoryConsents()
        ids = iter(("1", "2", "3", "4", "5"))
        self.now = datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.service = IdentityRegistrationService(
            self.users, self.students, self.consents, FakeHasher(),
            clock=lambda: self.now, id_factory=lambda: next(ids),
        )

    def test_registers_general_user(self) -> None:
        user = self.service.register_user("ADMIN@EXAMPLE.COM", "password", Role.ADMIN)
        self.assertEqual(user.email, "admin@example.com")
        self.assertEqual(user.password_hash, "hashed:password")

    def test_registers_student_identity(self) -> None:
        user, student = self.service.register_student("student@example.com", "password", "2026-001")
        self.assertIs(user.role, Role.STUDENT)
        self.assertEqual(student.user_id, user.id)

    def test_rejects_duplicate_email_and_code(self) -> None:
        self.service.register_student("student@example.com", "password", "2026-001")
        with self.assertRaises(ValueError):
            self.service.register_user("student@example.com", "password", Role.ADMIN)
        with self.assertRaises(ValueError):
            self.service.register_student("other@example.com", "password", "2026-001")

    def test_grants_and_revokes_versioned_consent(self) -> None:
        _, student = self.service.register_student("student@example.com", "password", "2026-001")
        consent = self.service.grant_consent(student.id, "privacy-v1")
        self.assertTrue(consent.is_active)
        with self.assertRaises(RuntimeError): self.service.grant_consent(student.id, "privacy-v1")
        revoked = self.service.revoke_consent(student.id)
        self.assertFalse(revoked.is_active)


if __name__ == "__main__": unittest.main()
