from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ParticipantKind(str, Enum):
    ADULT = "adult"
    CHILD = "child"


ADULT_AGE = 18
MIN_CHILD_AGE = 1
MAX_AGE = 120


def kind_for_age(age_years: int) -> ParticipantKind:
    return ParticipantKind.ADULT if age_years >= ADULT_AGE else ParticipantKind.CHILD


@dataclass(frozen=True, slots=True)
class Participant:
    """Persona analizada en una sesión. No tiene cuenta, nombre, DNI, foto ni
    datos del tutor: se identifica solo por un código aleatorio y su edad en
    años. La equivalencia entre el código y la persona está en una ficha de
    papel que custodia el docente; el sistema no puede recuperarla.

    notes es texto libre en claro solo en memoria; la persistencia lo cifra.
    age_years es nulo solo en participantes registrados antes de pedir la edad.
    authorization_revoked_at marca que el participante o su tutor retiró una
    autorización: no hay sesiones nuevas y el docente decide su eliminación.
    """

    id: str
    code: str
    kind: ParticipantKind | str
    registered_by_user_id: str
    created_at: datetime
    notes: str | None = None
    deletion_requested_at: datetime | None = None
    deletion_requested_by_user_id: str | None = None
    age_years: int | None = None
    authorization_revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("id", "code", "registered_by_user_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} no puede estar vacío")
            object.__setattr__(self, name, value.strip())
        object.__setattr__(self, "kind", ParticipantKind(self.kind))
        if self.age_years is not None:
            if isinstance(self.age_years, bool) or not isinstance(self.age_years, int):
                raise TypeError("age_years debe ser un entero")
            if not MIN_CHILD_AGE <= self.age_years <= MAX_AGE:
                raise ValueError(f"La edad debe estar entre {MIN_CHILD_AGE} y {MAX_AGE} años")
            if kind_for_age(self.age_years) is not self.kind:
                raise ValueError("Un participante adulto tiene 18 años o más; un niño o niña, menos de 18")
        for name in ("created_at", "deletion_requested_at", "authorization_revoked_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")
        if (self.deletion_requested_at is None) != (self.deletion_requested_by_user_id is None):
            raise ValueError("La solicitud de eliminación requiere fecha y solicitante")
        if self.notes is not None:
            notes = self.notes.strip()
            object.__setattr__(self, "notes", notes or None)
