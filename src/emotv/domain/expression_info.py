from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# Clases que produce FER+; el catálogo informativo tiene una entrada por cada una.
EXPRESSION_KEYS = ("neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt")

COMMON_LIMITATION = (
    "El reconocimiento facial estima una expresión a partir de la imagen y no determina "
    "por sí mismo el estado emocional ni psicológico de la persona."
)

LABEL_MAX_LENGTH = 60
TEXT_MIN_LENGTH = 20
TEXT_MAX_LENGTH = 1200
TEXT_FIELDS = ("what_it_is", "why_it_occurs", "facial_cues", "practice_tip", "limitation_note")


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"


@dataclass(frozen=True, slots=True)
class ExpressionInfo:
    """Texto educativo fijo y revisable sobre una expresión facial.

    Lo redacta y revisa el equipo de Psicología; nunca lo genera un LLM.
    """

    expression_key: str
    label_es: str
    what_it_is: str
    why_it_occurs: str
    facial_cues: str
    practice_tip: str
    limitation_note: str
    updated_at: datetime
    review_status: ReviewStatus | str = ReviewStatus.DRAFT
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.expression_key not in EXPRESSION_KEYS:
            raise ValueError(f"expresión desconocida: {self.expression_key}")
        label = self.label_es.strip()
        if not 1 <= len(label) <= LABEL_MAX_LENGTH:
            raise ValueError(f"label_es debe tener entre 1 y {LABEL_MAX_LENGTH} caracteres")
        object.__setattr__(self, "label_es", label)
        for field in TEXT_FIELDS:
            text = getattr(self, field).strip()
            if not TEXT_MIN_LENGTH <= len(text) <= TEXT_MAX_LENGTH:
                raise ValueError(
                    f"{field} debe tener entre {TEXT_MIN_LENGTH} y {TEXT_MAX_LENGTH} caracteres"
                )
            object.__setattr__(self, field, text)
        status = ReviewStatus(self.review_status)
        object.__setattr__(self, "review_status", status)
        for name in ("updated_at", "reviewed_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")
        # reviewed_by_user_id puede quedar nulo si la cuenta revisora se eliminó.
        if status is ReviewStatus.REVIEWED and self.reviewed_at is None:
            raise ValueError("una revisión registra cuándo se revisó")
        if status is ReviewStatus.DRAFT and (self.reviewed_at is not None or self.reviewed_by_user_id is not None):
            raise ValueError("un borrador no tiene revisión registrada")
