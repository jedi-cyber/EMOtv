from __future__ import annotations

from enum import Enum


class SessionState(str, Enum):
    """Estados posibles del ciclo de vida de una sesión emocional.

    IN_PROGRESS -> RECOGNIZED -> IN_PROGRESS (actividad) -> COMPLETED
                   RECOGNIZED -> COMPLETED (sin actividad)
    """

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    RECOGNIZED = "recognized"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActivityOutcome(str, Enum):
    """Resultado de la actividad corporal, guardado en exercise_result."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
