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
    crea el administrador para toda la Facultad. Usuario: imagen propia que un
    usuario sube para sus protocolos; no se usa hasta que su docente la revisa."""

    GROUP = "group"
    INSTITUTION = "institution"
    USER = "user"


class StimulusAudience(str, Enum):
    """Para quién es una imagen. «Para niños» equivale a intensidad leve y sirve
    en protocolos de niños y de adultos; «Para adultos», solo en los de adultos."""

    CHILDREN = "children"
    ADULTS = "adults"


AUDIENCE_INTENSITY = {"children": "mild", "adults": "moderate"}


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
    # Imágenes propias: la detección automática dudó, lote de subida, aviso de
    # vencimiento y eliminación (sin archivo; queda solo si algo la nombra).
    possible_person: bool = False
    upload_batch_id: str | None = None
    expiry_notified_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("id", "title", "category", "origin", "license", "owner_user_id", "content_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
            object.__setattr__(self, name, value.strip())
        kind = StimulusKind(self.kind)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "intensity", StimulusIntensity(self.intensity))
        scope = StimulusScope(self.scope)
        object.__setattr__(self, "scope", scope)
        if isinstance(self.min_age, bool) or not isinstance(self.min_age, int):
            raise TypeError("min_age debe ser un entero")
        if not MIN_STIMULUS_AGE <= self.min_age <= MAX_STIMULUS_AGE:
            raise ValueError(f"La edad mínima debe estar entre {MIN_STIMULUS_AGE} y {MAX_STIMULUS_AGE} años")
        expression = (self.expected_expression or "").strip() or None
        if kind is StimulusKind.EMOTIONAL:
            if scope is StimulusScope.USER and expression is None:
                pass  # una imagen propia no indica expresión esperada
            elif expression not in EXPRESSION_KEYS:
                raise ValueError("Un estímulo emocional indica la expresión que se espera provocar")
        elif expression is not None:
            raise ValueError("Una imagen abstracta no tiene expresión esperada")
        object.__setattr__(self, "expected_expression", expression)
        if (self.approved_at is None) != (self.approved_by_user_id is None):
            raise ValueError("La aprobación requiere fecha y quien aprueba")
        for name in ("created_at", "approved_at", "expiry_notified_at", "deleted_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")

    @property
    def approved(self) -> bool:
        return self.approved_at is not None

    @property
    def audience(self) -> StimulusAudience:
        return StimulusAudience.CHILDREN if self.intensity is StimulusIntensity.MILD else StimulusAudience.ADULTS

    @property
    def pending(self) -> bool:
        """Imagen propia que su docente todavía no revisó: se muestra «En revisión»."""
        return self.scope is StimulusScope.USER and not self.approved and self.deleted_at is None

    @property
    def usable(self) -> bool:
        """Se puede elegir en un protocolo: vigente, no eliminada y, si es una
        imagen propia, aprobada por el docente."""
        return (self.active and self.deleted_at is None
                and (self.approved or self.scope is not StimulusScope.USER))

    @property
    def suitable_for_children(self) -> bool:
        """Con niños solo estímulos leves («Para niños»), aprobados y vigentes. La
        edad de la persona no se registra, así que min_age no se usa para filtrar."""
        return self.usable and self.approved and self.intensity is StimulusIntensity.MILD
