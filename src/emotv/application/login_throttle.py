from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from emotv.application.ports.login_attempt_repository import LoginAttemptRepository
from emotv.config import LoginLimits

RETENTION = timedelta(hours=24)


def hash_email(email: str) -> str:
    """El correo no se guarda en claro: solo su SHA-256 normalizado."""

    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


class LoginThrottle:
    """Limita fallos de inicio de sesión por correo+IP y por IP.

    El contador de correo+IP se reinicia con un acceso correcto. El de IP no:
    si se reiniciara, alguien podría intercalar accesos con su propia cuenta
    para probar contraseñas de otras sin límite.
    """

    def __init__(self, repository: LoginAttemptRepository, limits: LoginLimits,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.repository = repository
        self.limits = limits
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def window(self) -> timedelta:
        return timedelta(minutes=self.limits.window_minutes)

    def is_blocked(self, email: str, ip: str) -> bool:
        since = self.clock() - self.window
        return (self.repository.count_ip_failures(ip, since) >= self.limits.max_failures_per_ip
                or self.repository.count_account_failures(hash_email(email), ip, since)
                >= self.limits.max_failures_per_account)

    def record(self, email: str, ip: str, success: bool) -> None:
        now = self.clock()
        self.repository.record(hash_email(email), ip, success, now, now - RETENTION)
