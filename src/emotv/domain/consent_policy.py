from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ConsentPolicy:
    id: str
    code: str
    version: str
    title: str
    content: str
    effective_at: datetime
    is_demo: bool = False
    approved: bool = False
    is_active: bool = False

    def __post_init__(self) -> None:
        if not all((self.id.strip(), self.code.strip(), self.version.strip(),
                    self.title.strip(), self.content.strip())):
            raise ValueError("La política requiere código, versión, título y contenido")
        if self.effective_at.tzinfo is None:
            raise ValueError("effective_at debe incluir zona horaria")
        if len(self.id) > 64:
            raise ValueError("id de política demasiado largo")
