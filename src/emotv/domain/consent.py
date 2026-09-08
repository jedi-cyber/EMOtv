from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    id: str
    student_id: str
    policy_version: str
    granted_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        for field in ("id", "student_id", "policy_version"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError(f"{field} no puede estar vacío")
            object.__setattr__(self, field, value)
        if self.granted_at.tzinfo is None:
            raise ValueError("granted_at debe incluir zona horaria")
        if self.revoked_at is not None:
            if self.revoked_at.tzinfo is None or self.revoked_at < self.granted_at:
                raise ValueError("revoked_at no es válido")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
