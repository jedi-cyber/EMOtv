from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol as Interface

from emotv.domain.protocol import Protocol
from emotv.domain.stimulus import Stimulus


class StimulusRepository(Interface):
    def add(self, stimulus: Stimulus, image: bytes) -> Stimulus: ...

    def save(self, stimulus: Stimulus) -> Stimulus:
        """Actualiza los datos; la imagen no cambia."""
        ...

    def get(self, stimulus_id: str) -> Stimulus | None: ...

    def get_image(self, stimulus_id: str) -> tuple[str, bytes] | None: ...

    def list_visible(self, group_owner_ids: Iterable[str]) -> tuple[Stimulus, ...]:
        """Los institucionales y los de grupo creados por esas cuentas."""
        ...


class ProtocolRepository(Interface):
    def add(self, protocol: Protocol) -> Protocol: ...

    def replace(self, protocol: Protocol) -> Protocol:
        """Reemplaza una versión que nunca se usó (datos y estímulos)."""
        ...

    def add_version(self, previous_id: str, superseded_at: datetime, protocol: Protocol) -> Protocol:
        """Marca la versión anterior como reemplazada y guarda la nueva, en una transacción."""
        ...

    def get(self, protocol_id: str) -> Protocol | None: ...

    def list_current(self, owner_ids: Iterable[str]) -> tuple[Protocol, ...]: ...

    def is_used(self, protocol_id: str) -> bool:
        """Si alguna sesión aplicó esta versión."""
        ...
