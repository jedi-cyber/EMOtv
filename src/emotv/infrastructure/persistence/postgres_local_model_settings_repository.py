from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.local_model_settings import LocalModelSettings
from emotv.infrastructure.persistence.models import LocalModelSettingsRecord

SETTINGS_ROW_ID = 1


class PostgresLocalModelSettingsRepository:
    """Lee y guarda la única fila de configuración de modelos locales."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory debe ser invocable")
        self._session_factory = session_factory

    def get(self) -> LocalModelSettings | None:
        with self._session_factory() as database_session:
            record = database_session.get(LocalModelSettingsRecord, SETTINGS_ROW_ID)
            return None if record is None else _to_domain(record)

    def save(self, settings: LocalModelSettings) -> LocalModelSettings:
        with self._session_factory.begin() as database_session:
            record = database_session.get(LocalModelSettingsRecord, SETTINGS_ROW_ID)
            if record is None:
                record = LocalModelSettingsRecord(id=SETTINGS_ROW_ID)
                database_session.add(record)
            record.default_model_id = settings.default_model_id
            record.changed_by_user_id = settings.changed_by_user_id
            record.changed_at = settings.changed_at
            record.fallback_model_id = settings.fallback_model_id
            record.fallback_at = settings.fallback_at
        return settings


class InMemoryLocalModelSettingsRepository:
    """Configuración en memoria para pruebas y para el arranque sin base de datos."""

    def __init__(self, settings: LocalModelSettings | None = None) -> None:
        self._settings = settings

    def get(self) -> LocalModelSettings | None:
        return self._settings

    def save(self, settings: LocalModelSettings) -> LocalModelSettings:
        self._settings = settings
        return settings


def _to_domain(record: LocalModelSettingsRecord) -> LocalModelSettings:
    return LocalModelSettings(
        default_model_id=record.default_model_id,
        changed_by_user_id=record.changed_by_user_id,
        changed_at=_as_aware(record.changed_at),
        fallback_model_id=record.fallback_model_id,
        fallback_at=_as_aware(record.fallback_at),
    )


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None or (value.tzinfo is not None and value.utcoffset() is not None):
        return value
    return value.replace(tzinfo=timezone.utc)
