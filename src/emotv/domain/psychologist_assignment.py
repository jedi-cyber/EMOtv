from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PsychologistAssignment:
    """Autoriza a un psicólogo a consultar los datos de un estudiante."""

    psychologist_user_id: str
    student_id: str
    assigned_at: datetime
    assigned_by_user_id: str | None = None

    def __post_init__(self) -> None:
        if not self.psychologist_user_id.strip() or not self.student_id.strip():
            raise ValueError("La asignación requiere psicólogo y estudiante")
        if self.assigned_at.tzinfo is None:
            raise ValueError("assigned_at debe incluir zona horaria")
