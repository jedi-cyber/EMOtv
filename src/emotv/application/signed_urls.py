"""URLs firmadas de corta duración para las imágenes de estímulos del aplicativo móvil.

La firma (HMAC-SHA256) cubre la cuenta, la sesión, el estímulo y el vencimiento:
no se puede reutilizar para otra sesión, otra cuenta ni después de vencer. La
clave se deriva del secreto de los tokens con un prefijo propio, así una firma
nunca sirve como token ni al revés.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
import hmac

STIMULUS_URL_SECONDS = 120


class StimulusUrlSigner:
    def __init__(self, secret: str, clock: Callable[[], datetime] | None = None,
                 seconds: int = STIMULUS_URL_SECONDS) -> None:
        self._key = hashlib.sha256(b"emotv-stimulus-url:" + secret.encode("utf-8")).digest()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.seconds = seconds

    def _signature(self, user_id: str, session_id: str, stimulus_id: str, expires: int) -> str:
        message = "\n".join((user_id, session_id, stimulus_id, str(expires))).encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def sign(self, user_id: str, session_id: str, stimulus_id: str) -> tuple[int, str]:
        """Vencimiento (segundos Unix) y firma."""
        expires = int(self.clock().timestamp()) + self.seconds
        return expires, self._signature(user_id, session_id, stimulus_id, expires)

    def verify(self, user_id: str, session_id: str, stimulus_id: str, expires: int, signature: str) -> bool:
        if expires < int(self.clock().timestamp()):
            return False
        return hmac.compare_digest(self._signature(user_id, session_id, stimulus_id, expires), signature)
