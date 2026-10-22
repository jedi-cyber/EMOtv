from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

MAX_EXPOSURE_SECONDS = 120
MAX_STEPS = 30


@dataclass(frozen=True, slots=True)
class ProtocolStep:
    """Un estímulo de la secuencia. capture_after_seconds es el tiempo hasta la
    captura automática de la expresión estimada, dentro de la exposición.
    record_verbal_response solo aplica a imágenes abstractas: se registra lo que
    el participante dice ver, sin interpretarlo. shown_before_analyzer (solo
    abstractas) la muestra antes de la calibración, sin capturas."""

    stimulus_id: str
    exposure_seconds: int
    capture_after_seconds: int
    record_verbal_response: bool = False
    shown_before_analyzer: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.stimulus_id, str) or not self.stimulus_id.strip():
            raise ValueError("Cada paso indica un estímulo")
        object.__setattr__(self, "stimulus_id", self.stimulus_id.strip())
        for name in ("exposure_seconds", "capture_after_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} debe ser un entero de segundos")
        if not 1 <= self.exposure_seconds <= MAX_EXPOSURE_SECONDS:
            raise ValueError(f"La exposición dura entre 1 y {MAX_EXPOSURE_SECONDS} segundos")
        if not 0 <= self.capture_after_seconds <= self.exposure_seconds:
            raise ValueError("La captura automática ocurre durante la exposición")


@dataclass(frozen=True, slots=True)
class Protocol:
    """Una versión de un protocolo. Las versiones de un mismo protocolo
    comparten family_id; la vigente es la que no tiene superseded_at.

    Un protocolo para niños se usa solo con la aprobación del docente; editarlo
    o crear una versión nueva vuelve a pedirla. Uno usado en una sesión no se
    edita: se crea una versión nueva.
    """

    id: str
    family_id: str
    version: int
    owner_user_id: str
    name: str
    description: str
    for_children: bool
    created_at: datetime
    steps: tuple[ProtocolStep, ...] = field(default_factory=tuple)
    pre_questionnaire_id: str | None = None
    post_questionnaire_id: str | None = None
    approved_at: datetime | None = None
    approved_by_user_id: str | None = None
    superseded_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("id", "family_id", "owner_user_id", "name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
            object.__setattr__(self, name, value.strip())
        object.__setattr__(self, "description", (self.description or "").strip())
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version debe ser un entero positivo")
        steps = tuple(self.steps)
        if not 1 <= len(steps) <= MAX_STEPS:
            raise ValueError(f"Un protocolo tiene entre 1 y {MAX_STEPS} estímulos")
        object.__setattr__(self, "steps", steps)
        for name in ("pre_questionnaire_id", "post_questionnaire_id"):
            object.__setattr__(self, name, (getattr(self, name) or "").strip() or None)
        if (self.approved_at is None) != (self.approved_by_user_id is None):
            raise ValueError("La aprobación requiere fecha y quien aprueba")
        for name in ("created_at", "approved_at", "superseded_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")

    @property
    def approved(self) -> bool:
        return self.approved_at is not None

    @property
    def current(self) -> bool:
        return self.superseded_at is None
