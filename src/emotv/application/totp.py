"""Códigos de un solo uso por tiempo (TOTP, RFC 6238) con la biblioteca estándar.

Compatibles con Google Authenticator, Microsoft Authenticator y similares:
HMAC-SHA1, intervalos de 30 s y 6 dígitos. Se acepta un intervalo antes y uno
después para tolerar relojes algo desfasados.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from datetime import datetime
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6
ISSUER = "EMOtv"


def generate_secret() -> str:
    """Clave nueva de 160 bits en base32, como la piden las aplicaciones autenticadoras."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def time_step(at: datetime) -> int:
    return int(at.timestamp()) // STEP_SECONDS


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def matching_step(secret: str, code: str, at: datetime, *, after: int | None = None) -> int | None:
    """Intervalo al que corresponde el código, o None. ``after`` descarta los
    intervalos ya usados para que un código no sirva dos veces."""
    code = "".join(code.split())
    if len(code) != DIGITS or not code.isdigit():
        return None
    current = time_step(at)
    for step in (current - 1, current, current + 1):
        if after is not None and step <= after:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, email: str) -> str:
    """Enlace otpauth:// que las aplicaciones autenticadoras importan."""
    label = quote(f"{ISSUER}:{email}")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={ISSUER}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}")
