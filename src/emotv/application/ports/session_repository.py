from __future__ import annotations

from typing import Protocol, runtime_checkable

from emotv.domain.session import EmotionalSession


@runtime_checkable
class SessionRepository(Protocol):
    """Puerto de persistencia para sesiones emocionales."""

    def save(self, session: EmotionalSession) -> EmotionalSession:
        """Guarda una sesión y devuelve la representación persistida."""

        ...

    def get_by_id(self, session_id: str) -> EmotionalSession | None:
        """Recupera una sesión o devuelve ``None`` si no existe."""

        ...

    def list_all(self) -> tuple[EmotionalSession, ...]:
        """Devuelve todas las sesiones en el orden definido por el repositorio."""

        ...

    def list_by_student(self, student_id: str) -> tuple[EmotionalSession, ...]:
        """Devuelve las sesiones asociadas al estudiante indicado."""

        ...
