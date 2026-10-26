from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from emotv.domain.expression_info import EXPRESSION_KEYS


class StimulusKind(str, Enum):
    EMOTIONAL = "emotional"
    ABSTRACT = "abstract"


class StimulusIntensity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"


class StimulusScope(str, Enum):
    """Grupo: lo crea un docente para los usuarios de su grupo. Institución: lo
    crea el administrador para toda la Facultad."""

    GROUP = "group"
    INSTITUTION = "institution"


MIN_STIMULUS_AGE = 1
MAX_STIMULUS_AGE = 99


@dataclass(frozen=True, slots=True)
class Stimulus:
    """Imagen del banco de estímulos. Nunca es una foto de una persona evaluada.

    Solo se muestra y se registra: el sistema no relaciona una imagen abstracta
    con ninguna condición. expected_expression existe solo en los emocionales.
    origin y license son obligatorios; las abstractas son de creación propia o
    con una licencia que lo permita, nunca láminas de pruebas proyectivas.
    """

    id: str
    title: str
    kind: StimulusKind | str
    category: str
    intensity: StimulusIntensity | str
    min_age: int
    origin: str
    license: str
    scope: StimulusScope | str
    owner_user_id: str
    content_type: str
    created_at: datetime
    expected_expression: str | None = None
    approved_at: datetime | None = None
    approved_by_user_id: str | None = None
    active: bool = True

    def __post_init__(self) -> None:
        for name in ("id", "title", "category", "origin", "license", "owner_user_id", "content_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
            object.__setattr__(self, name, value.strip())
        kind = StimulusKind(self.kind)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "intensity", StimulusIntensity(self.intensity))
        object.__setattr__(self, "scope", StimulusScope(self.scope))
        if isinstance(self.min_age, bool) or not isinstance(self.min_age, int):
            raise TypeError("min_age debe ser un entero")
        if not MIN_STIMULUS_AGE <= self.min_age <= MAX_STIMULUS_AGE:
            raise ValueError(f"La edad mínima debe estar entre {MIN_STIMULUS_AGE} y {MAX_STIMULUS_AGE} años")
        expression = (self.expected_expression or "").strip() or None
        if kind is StimulusKind.EMOTIONAL:
            if expression not in EXPRESSION_KEYS:
                raise ValueError("Un estímulo emocional indica la expresión que se espera provocar")
        elif expression is not None:
            raise ValueError("Una imagen abstracta no tiene expresión esperada")
        object.__setattr__(self, "expected_expression", expression)
        if (self.approved_at is None) != (self.approved_by_user_id is None):
            raise ValueError("La aprobación requiere fecha y quien aprueba")
        for name in ("created_at", "approved_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")

    @property
    def approved(self) -> bool:
        return self.approved_at is not None

    @property
    def suitable_for_children(self) -> bool:
        """Con niños solo estímulos leves, aprobados y vigentes. La edad de la
        persona no se registra, así que min_age no se usa para filtrar."""
        return self.active and self.approved and self.intensity is StimulusIntensity.MILD
