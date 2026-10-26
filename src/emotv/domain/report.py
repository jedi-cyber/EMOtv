"""Reporte de una sesión, redactado por quien la condujo y revisado por su
docente.

Las expresiones del reporte son estimaciones de apoyo, no una evaluación. El
texto y los comentarios se guardan cifrados; el historial no guarda contenido.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

MAX_NARRATIVE = 8000
MAX_COMMENT = 2000
ESTIMATES_NOTICE = ("Las expresiones de este reporte son estimaciones de apoyo de un modelo automático sobre el "
                    "rostro visible. No son una evaluación ni indican lo que la persona sentía.")


class ReportStatus(str, Enum):
    DRAFT = "draft"                          # borrador
    SUBMITTED = "submitted"                  # enviado a revisión
    CHANGES_REQUESTED = "changes_requested"  # con observaciones
    APPROVED = "approved"


EDITABLE = frozenset({ReportStatus.DRAFT, ReportStatus.CHANGES_REQUESTED})


class ReportSection(str, Enum):
    TIMELINE = "timeline"
    METRICS = "metrics"
    QUESTIONNAIRES = "questionnaires"
    NARRATIVE = "narrative"
    GENERAL = "general"


class ReportAction(str, Enum):
    CREATED = "created"
    EDITED = "edited"
    SUBMITTED = "submitted"
    COMMENTED = "commented"
    RETURNED = "returned"
    APPROVED = "approved"
    CLOSED = "closed"            # un docente cierra su propio reporte: queda aprobado
    NEW_VERSION = "new_version"
    PRINTED = "printed"


def _clean(text: str | None, limit: int, name: str) -> str:
    value = (text or "").strip()
    if len(value) > limit:
        raise ValueError(f"{name} supera los {limit} caracteres")
    return value


@dataclass(frozen=True, slots=True)
class SessionReport:
    """Una versión del reporte; las de una sesión comparten family_id. narrative
    está en claro solo en memoria."""

    id: str
    family_id: str
    version: int
    session_id: str
    author_user_id: str
    status: ReportStatus | str
    narrative: str
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    approved_by_user_id: str | None = None
    superseded_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ReportStatus(self.status))
        object.__setattr__(self, "narrative", _clean(self.narrative, MAX_NARRATIVE, "El texto del reporte"))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version debe ser un entero positivo")
        if (self.status is ReportStatus.APPROVED) != (self.approved_at is not None):
            raise ValueError("Solo un reporte aprobado tiene fecha de aprobación")
        if (self.approved_at is None) != (self.approved_by_user_id is None):
            raise ValueError("La aprobación requiere fecha y quien aprueba")

    @property
    def current(self) -> bool:
        return self.superseded_at is None


@dataclass(frozen=True, slots=True)
class ReportComment:
    id: str
    report_id: str
    section: ReportSection | str
    text: str
    author_user_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "section", ReportSection(self.section))
        text = _clean(self.text, MAX_COMMENT, "El comentario")
        if not text:
            raise ValueError("Escribe el comentario")
        object.__setattr__(self, "text", text)


@dataclass(frozen=True, slots=True)
class ReportEvent:
    """Historial del reporte: quién hizo qué y cuándo, sin contenido."""

    id: str
    report_id: str
    action: ReportAction | str
    actor_user_id: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", ReportAction(self.action))
