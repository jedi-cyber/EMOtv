from enum import Enum


class SessionType(str, Enum):
    """Público de la sesión; lo fija el protocolo o, sin protocolo, quien la conduce."""

    # Quien inicia sesión se analiza a sí mismo.
    OWN = "propia"
    # Con una persona adulta que firmó su autorización.
    ADULT = "adulto"
    # Con un niño o niña: su tutor autorizó por escrito y está presente.
    CHILD = "infantil"
