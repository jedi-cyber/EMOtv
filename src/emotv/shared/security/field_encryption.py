"""Cifrado de campos sensibles en reposo con Fernet (AES-128-CBC + HMAC-SHA256).

Se cifran notas libres, marcadores con texto, respuestas de cuestionarios,
respuestas a imágenes abstractas, comentarios del docente y texto de reportes.
SENSITIVE_DATA_KEY admite varias claves separadas por comas: la primera cifra y
todas descifran, así una clave nueva puede entrar antes de retirar la anterior.
Genera una clave con:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

from collections.abc import Sequence

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class FieldEncryptionError(ValueError):
    """Clave inválida o texto cifrado que ninguna clave configurada puede leer."""


class FieldCipher:
    def __init__(self, keys: Sequence[str]) -> None:
        if not keys:
            raise FieldEncryptionError("Se requiere al menos una clave en SENSITIVE_DATA_KEY")
        try:
            self._fernet = MultiFernet([Fernet(key.encode("ascii")) for key in keys])
        except (ValueError, TypeError) as error:
            # Sin el valor de la clave en el mensaje.
            raise FieldEncryptionError("SENSITIVE_DATA_KEY contiene una clave Fernet inválida") from error

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str | None) -> str | None:
        if token is None:
            return None
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError) as error:
            raise FieldEncryptionError("No se pudo descifrar un campo con las claves configuradas") from error

    def rotate(self, token: str | None) -> str | None:
        """Vuelve a cifrar con la primera clave (para completar una rotación)."""
        if token is None:
            return None
        try:
            return self._fernet.rotate(token.encode("ascii")).decode("ascii")
        except InvalidToken as error:
            raise FieldEncryptionError("No se pudo rotar un campo con las claves configuradas") from error


def create_field_cipher(keys: Sequence[str]) -> FieldCipher | None:
    """FieldCipher con las claves dadas, o None si no hay ninguna configurada."""
    return FieldCipher(keys) if keys else None
