from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from emotv.domain.role import Role


@dataclass(frozen=True, slots=True)
class User:
    id: str
    email: str
    password_hash: str
    role: Role | str
    created_at: datetime
    is_active: bool = True

    def __post_init__(self) -> None:
        user_id, email = self.id.strip(), self.email.strip().lower()
        if not user_id or not email or "@" not in email:
            raise ValueError("id y email deben ser válidos")
        if not self.password_hash.strip():
            raise ValueError("password_hash no puede estar vacío")
        role = Role(self.role)
        if self.created_at.tzinfo is None:
            raise ValueError("created_at debe incluir zona horaria")
        object.__setattr__(self, "id", user_id)
        object.__setattr__(self, "email", email)
        object.__setattr__(self, "role", role)


@dataclass(frozen=True, slots=True)
class Student:
    id: str
    user_id: str
    student_code: str

    def __post_init__(self) -> None:
        for field in ("id", "user_id", "student_code"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError(f"{field} no puede estar vacío")
            object.__setattr__(self, field, value)
