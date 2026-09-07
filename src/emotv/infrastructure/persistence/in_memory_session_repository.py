from __future__ import annotations

from threading import RLock

from emotv.domain.session import EmotionalSession


class InMemorySessionRepository:
    """Almacena sesiones durante la vida del proceso actual."""

    def __init__(self) -> None:
        self._sessions: dict[str, EmotionalSession] = {}
        self._lock = RLock()

    def save(self, session: EmotionalSession) -> EmotionalSession:
        if not isinstance(session, EmotionalSession):
            raise TypeError("session debe ser una EmotionalSession")
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get_by_id(self, session_id: str) -> EmotionalSession | None:
        normalized_id = self._normalize_id(session_id)
        with self._lock:
            return self._sessions.get(normalized_id)

    def list_all(self) -> tuple[EmotionalSession, ...]:
        with self._lock:
            return tuple(self._sessions.values())

    @staticmethod
    def _normalize_id(session_id: str) -> str:
        if not isinstance(session_id, str):
            raise TypeError("session_id debe ser str")
        normalized_id = session_id.strip()
        if not normalized_id:
            raise ValueError("session_id no puede estar vacío")
        return normalized_id
