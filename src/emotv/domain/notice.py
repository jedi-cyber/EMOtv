from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_NOTICE_LENGTH = 800


@dataclass(frozen=True, slots=True)
class UserNotice:
    """Aviso para una cuenta: una imagen eliminada (con el motivo del docente),
    una imagen por vencer o un protocolo que necesita una imagen. Nunca nombra a
    una persona evaluada ni contiene resultados."""

    id: str
    user_id: str
    message: str
    created_at: datetime
    read_at: datetime | None = None

    def __post_init__(self) -> None:
        message = (self.message or "").strip()
        if not message:
            raise ValueError("El aviso necesita un texto")
        object.__setattr__(self, "message", message[:MAX_NOTICE_LENGTH])
