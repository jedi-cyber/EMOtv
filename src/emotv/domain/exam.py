"""Examen simulado: sesión grupal que agrupa una sesión individual por estación.

El docente lo crea con un clic, confirma de una vez que recibió los
consentimientos firmados, lo inicia y lo termina. Cada estación se une con el
código del examen; ninguna persona se registra. El consentimiento queda en
cada sesión (authorization_confirmed_at): una estación que se une después de
la confirmación espera una nueva.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

JOIN_CODE_LENGTH = 6
JOIN_CODE_ALPHABET = frozenset("ABCDEFGHJKMNPQRSTUVWXYZ23456789")  # sin 0/O ni 1/I/L


class ExamState(str, Enum):
    OPEN = "open"                 # las estaciones se unen; todavía no empieza
    IN_PROGRESS = "in_progress"   # el docente lo inició
    CLOSED = "closed"             # el docente lo terminó


@dataclass(frozen=True, slots=True)
class Exam:
    id: str
    owner_user_id: str
    protocol_id: str
    join_code: str
    created_at: datetime
    state: ExamState | str = ExamState.OPEN
    # Última vez que el docente confirmó los consentimientos de las estaciones unidas.
    consent_confirmed_at: datetime | None = None
    started_at: datetime | None = None
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("id", "owner_user_id", "protocol_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
            object.__setattr__(self, name, value.strip())
        code = self.join_code.strip().upper() if isinstance(self.join_code, str) else ""
        if len(code) != JOIN_CODE_LENGTH or not set(code) <= JOIN_CODE_ALPHABET:
            raise ValueError(f"El código del examen tiene {JOIN_CODE_LENGTH} letras o números")
        object.__setattr__(self, "join_code", code)
        state = ExamState(self.state)
        object.__setattr__(self, "state", state)
        for name in ("created_at", "consent_confirmed_at", "started_at", "closed_at"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, datetime) or value.tzinfo is None
                                      or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")
        if self.created_at is None:
            raise ValueError("created_at es obligatorio")
        if (state is ExamState.IN_PROGRESS) and self.started_at is None:
            raise ValueError("Un examen en curso registra cuándo empezó")
        if (state is ExamState.OPEN) and self.started_at is not None:
            raise ValueError("Un examen sin iniciar no tiene hora de inicio")
        if (state is ExamState.CLOSED) != (self.closed_at is not None):
            raise ValueError("Solo un examen terminado registra cuándo terminó")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("Un examen no empieza antes de crearse")
        if self.closed_at is not None and self.closed_at < (self.started_at or self.created_at):
            raise ValueError("Un examen no termina antes de empezar")

    @property
    def accepts_stations(self) -> bool:
        """Una estación puede unirse mientras el examen no haya terminado."""
        return self.state is not ExamState.CLOSED
