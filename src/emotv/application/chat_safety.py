"""Filtro de riesgo previo a Emi.

Lista corta y deliberadamente conservadora: si una pregunta coincide, no se
envía al webhook y se responde con un mensaje fijo que deriva a personas de
confianza, profesionales o servicios de emergencia. No es un detector clínico.
"""
from __future__ import annotations

import re
import unicodedata

RISK_CATEGORY = "filtro_riesgo"

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
