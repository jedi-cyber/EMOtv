from __future__ import annotations

from typing import Protocol

from emotv.domain.local_model_settings import LocalModelSettings


class LocalModelSettingsRepository(Protocol):
    def get(self) -> LocalModelSettings | None: ...

    def save(self, settings: LocalModelSettings) -> LocalModelSettings: ...
