from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ParticipantKind(str, Enum):
    ADULT = "adult"
    CHILD = "child"


@dataclass(frozen=True, slots=True)
class Participant:
    """Persona analizada en una sesión. No tiene cuenta, nombre, DNI ni foto:
    se identifica solo por un código aleatorio.

    notes es texto libre en claro solo en memoria; la persistencia lo cifra.
    """

    id: str
    code: str
    kind: ParticipantKind | str
    registered_by_user_id: str
    created_at: datetime
    notes: str | None = None
    deletion_requested_at: datetime | None = None
    deletion_requested_by_user_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("id", "code", "registered_by_user_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} no puede estar vacío")
            object.__setattr__(self, name, value.strip())
        object.__setattr__(self, "kind", ParticipantKind(self.kind))
        for name in ("created_at", "deletion_requested_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")
        if (self.deletion_requested_at is None) != (self.deletion_requested_by_user_id is None):
            raise ValueError("La solicitud de eliminación requiere fecha y solicitante")
        if self.notes is not None:
            notes = self.notes.strip()
            object.__setattr__(self, "notes", notes or None)
