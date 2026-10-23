"""Filtros previos a Emi: riesgo e identificadores.

Filtro de riesgo: lista corta y deliberadamente conservadora; si una pregunta
coincide, no se envía al webhook y se responde con un mensaje fijo que deriva a
personas de confianza, profesionales o servicios de emergencia. No es un
detector clínico.

Filtro de identificadores: si la pregunta contiene un DNI (8 dígitos), un correo
o un teléfono, tampoco se envía; se pide quitar los datos que identifiquen a una
persona. El texto no se reescribe ni se guarda: la persona decide cómo
reformularlo.
"""
from __future__ import annotations

import re
import unicodedata

RISK_CATEGORY = "filtro_riesgo"
IDENTIFIER_CATEGORY = "filtro_identificadores"
IDENTIFIER_MESSAGE = (
    "Tu mensaje no se envió porque parece incluir un DNI, un correo electrónico o un "
    "teléfono. Quita los datos que puedan identificar a una persona (nombres, documentos, "
    "contactos, datos de niños o familias) y vuelve a escribir tu pregunta."
)

RISK_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"\bsuicid",
    r"\bquitarme la vida\b",
    r"\bacabar con mi vida\b",
    r"\bmatarme\b",
    r"\b(me )?quiero morir(me)?\b",
    r"\bno quiero (seguir )?vivir\b",
    r"\bhacerme dano\b",
    r"\bautolesi",
    r"\bcortarme\b",
    r"\bmatar a (alguien|una persona|mi |mis )",
))


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents)


def is_risky(text: str) -> bool:
    normalized = normalize(text)
    return any(pattern.search(normalized) for pattern in RISK_PATTERNS)


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
# Secuencias de cifras con separadores habituales (espacios, guiones, puntos, paréntesis).
DIGIT_RUN = re.compile(r"\+?\(?\d[\d\s().-]*\d")
YEAR = re.compile(r"(19|20)\d\d")
DNI_DIGITS = 8
PHONE_DIGITS = range(7, 16)


def identifier_kind(text: str) -> str | None:
    """``"correo"``, ``"dni"``, ``"telefono"`` o ``None``. Nunca devuelve el dato.

    Es conservador: ante la duda bloquea, porque el mensaje se puede reescribir.
    Solo excluye las secuencias formadas por años (por ejemplo, «2024-2025»).
    """
    if EMAIL.search(text):
        return "correo"
    for match in DIGIT_RUN.finditer(text):
        groups = re.findall(r"\d+", match.group())
        if len(groups) > 1 and all(YEAR.fullmatch(group) for group in groups):
            continue
        digits = sum(len(group) for group in groups)
        if digits == DNI_DIGITS:
            return "dni"
        if digits in PHONE_DIGITS:
            return "telefono"
    return None


def has_identifier(text: str) -> bool:
    return identifier_kind(text) is not None
