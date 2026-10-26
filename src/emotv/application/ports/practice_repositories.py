from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol as Interface

from emotv.domain.notice import UserNotice
from emotv.domain.protocol import Protocol
from emotv.domain.stimulus import Stimulus


class StimulusRepository(Interface):
    def add(self, stimulus: Stimulus, image: bytes) -> Stimulus: ...

    def save(self, stimulus: Stimulus) -> Stimulus:
        """Actualiza los datos; la imagen no cambia."""
        ...

    def get(self, stimulus_id: str) -> Stimulus | None: ...

    def get_image(self, stimulus_id: str) -> tuple[str, bytes] | None: ...

    def list_visible(self, group_owner_ids: Iterable[str],
                     user_image_owner_id: str | None = None) -> tuple[Stimulus, ...]:
        """Los institucionales, los de grupo creados por esas cuentas y, si se
        indica, las imágenes propias aprobadas de esa cuenta. Nunca las eliminadas."""
        ...

    def list_user_images(self, owner_ids: Iterable[str]) -> tuple[Stimulus, ...]:
        """Imágenes propias (pendientes y aprobadas) de esas cuentas, sin las eliminadas."""
        ...

    def list_pending(self) -> tuple[Stimulus, ...]:
        """Todas las imágenes propias sin revisar, para su vencimiento."""
        ...

    def remove(self, stimulus_id: str, deleted_at: datetime) -> None:
        """Borra la imagen y su registro. Si una sesión o un protocolo la nombran,
        borra solo el archivo y conserva el registro marcado como eliminado."""
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

    def list_current_using(self, stimulus_id: str) -> tuple[Protocol, ...]:
        """Versiones vigentes que usan ese estímulo en algún paso."""
        ...


class NoticeRepository(Interface):
    def add(self, notice: UserNotice) -> UserNotice: ...

    def list_unread(self, user_id: str) -> tuple[UserNotice, ...]: ...

    def mark_read(self, notice_id: str, user_id: str, read_at: datetime) -> bool:
        """Marca como leído un aviso de esa cuenta; False si no es suyo o no existe."""
        ...
