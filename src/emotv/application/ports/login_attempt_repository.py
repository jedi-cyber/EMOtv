from __future__ import annotations

from datetime import datetime
from typing import Protocol


class LoginAttemptRepository(Protocol):
    """Registro de intentos de inicio de sesión compartido entre procesos."""

    def record(self, email_hash: str, ip: str, success: bool, at: datetime, purge_before: datetime) -> None:
        """Guarda un intento y elimina los registros anteriores a ``purge_before``."""
        ...

    def count_account_failures(self, email_hash: str, ip: str, since: datetime) -> int:
        """Fallos de correo+IP desde ``since`` posteriores al último acceso correcto."""
        ...

    def count_ip_failures(self, ip: str, since: datetime) -> int:
        ...
