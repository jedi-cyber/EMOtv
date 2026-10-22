from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class Grantor(str, Enum):
    """Quién firmó el formato en papel."""

    PARTICIPANT = "participant"  # el propio participante adulto
    GUARDIAN = "guardian"        # el padre, la madre o el tutor de un niño


class RevokedScope(str, Enum):
    """Qué se retiró: cualquiera de las tres bloquea las sesiones nuevas."""

    PARTICIPATION = "participation"
    CAMERA = "camera"
    ASSENT = "assent"


@dataclass(frozen=True, slots=True)
class ParticipantAuthorization:
    """Registro de un formato firmado en papel. No guarda nombres ni datos de
    quien firma: solo la versión del formato, la fecha y lo que autoriza.

    participation: participación y registro de la expresión estimada (a).
    camera: uso de la cámara (b).
    child_assent: asentimiento del niño o la niña, adaptado a su edad; nulo en
    adultos.
    """

    id: str
    participant_id: str
    form_version: str
    signed_on: date
    grantor: Grantor | str
    participation: bool
    camera: bool
    child_assent: bool | None
    recorded_by_user_id: str
    recorded_at: datetime
    revoked_at: datetime | None = None
    revoked_by_user_id: str | None = None
    revoked_party: Grantor | str | None = None
    revoked_scope: RevokedScope | str | None = None

    def __post_init__(self) -> None:
        for name in ("id", "participant_id", "form_version", "recorded_by_user_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} no puede estar vacío")
            object.__setattr__(self, name, value.strip())
        object.__setattr__(self, "grantor", Grantor(self.grantor))
        for name in ("participation", "camera"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} debe ser verdadero o falso")
        if self.child_assent is not None and not isinstance(self.child_assent, bool):
            raise TypeError("child_assent debe ser verdadero, falso o nulo")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at debe incluir zona horaria")
        if self.signed_on > self.recorded_at.date():
            raise ValueError("La fecha de firma no puede ser posterior a hoy")
        revocation = (self.revoked_at, self.revoked_by_user_id, self.revoked_party, self.revoked_scope)
        if any(value is None for value in revocation) and any(value is not None for value in revocation):
            raise ValueError("El retiro requiere fecha, quién lo registra, quién lo pidió y qué se retiró")
        if self.revoked_at is not None:
            object.__setattr__(self, "revoked_party", Grantor(self.revoked_party))
            object.__setattr__(self, "revoked_scope", RevokedScope(self.revoked_scope))

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None

    def allows_sessions(self, is_child: bool) -> bool:
        """(a) y (b) otorgadas y, en niños, el asentimiento; sin retiro."""
        return (not self.revoked and self.participation and self.camera
                and (not is_child or self.child_assent is True))
