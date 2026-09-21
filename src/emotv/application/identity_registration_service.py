from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from emotv.application.ports import (
    ConsentRepository,
    StudentRepository,
    UserRepository,
)
from emotv.domain import ConsentRecord, Role, Student, User


class PasswordHasher(Protocol):
    def hash_password(self, password: str) -> str: ...


class IdentityRegistrationService:
    """Coordina identidades y consentimientos sin conocer SQLAlchemy."""

    def __init__(
        self,
        users: UserRepository,
        students: StudentRepository,
        consents: ConsentRepository,
        password_hasher: PasswordHasher,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.users = users
        self.students = students
        self.consents = consents
        self.password_hasher = password_hasher
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: str(uuid4()))

    def register_user(self, email: str, password: str, role: Role | str,
                      *, must_change_password: bool = False) -> User:
        normalized_email = email.strip().lower()
        if self.users.get_by_email(normalized_email) is not None:
            raise ValueError("el correo ya está registrado")
        user = User(
            id=self._id("user"),
            email=normalized_email,
            password_hash=self.password_hasher.hash_password(password),
            role=Role(role),
            created_at=self.clock(),
            must_change_password=must_change_password,
        )
        return self.users.save(user)

    def register_student(
        self,
        email: str,
        password: str,
        student_code: str,
        *,
        must_change_password: bool = False,
    ) -> tuple[User, Student]:
        normalized_code = student_code.strip()
        if self.students.get_by_code(normalized_code) is not None:
            raise ValueError("el código de estudiante ya está registrado")
        user = self.register_user(email, password, Role.STUDENT,
                                  must_change_password=must_change_password)
        student = Student(
            id=self._id("student"),
            user_id=user.id,
            student_code=normalized_code,
        )
        return user, self.students.save(student)

    def grant_consent(
        self,
        student_id: str,
        policy_version: str,
    ) -> ConsentRecord:
        student = self.students.get_by_id(student_id)
        if student is None:
            raise KeyError(f"Estudiante no encontrado: {student_id}")
        current = self.consents.get_active_by_student(student.id)
        if current is not None and current.policy_version == policy_version.strip():
            raise RuntimeError("el estudiante ya tiene un consentimiento activo para esta versión")
        now = self.clock()
        if current is not None:
            self.consents.save(replace(current, revoked_at=max(now, current.granted_at)))
        consent = ConsentRecord(
            id=self._id("consent"),
            student_id=student.id,
            policy_version=policy_version,
            granted_at=now,
        )
        return self.consents.save(consent)

    def revoke_consent(self, student_id: str) -> ConsentRecord:
        consent = self.consents.get_active_by_student(student_id)
        if consent is None:
            raise RuntimeError("el estudiante no tiene consentimiento activo")
        return self.consents.save(replace(consent, revoked_at=self.clock()))

    def _id(self, prefix: str) -> str:
        value = self.id_factory().strip()
        if not value:
            raise ValueError("id_factory generó un ID vacío")
        return f"{prefix}-{value}"
