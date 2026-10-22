from enum import Enum


class SessionType(str, Enum):
    """A quién se analiza en la sesión; se guarda con ella."""

    # Quien inicia sesión se analiza a sí mismo; no hay participante.
    OWN = "propia"
    ADULT_PARTICIPANT = "participante_adulto"
    CHILD_PARTICIPANT = "participante_infantil"
