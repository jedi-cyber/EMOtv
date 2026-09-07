from __future__ import annotations

from enum import Enum


class SessionState(str, Enum):
    """Estados posibles del ciclo de vida de una sesión emocional."""

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
