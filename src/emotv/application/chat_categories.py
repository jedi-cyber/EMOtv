"""Categorías de Emi: las del clasificador del workflow EMI y las de los filtros de FastAPI.

El contador de rechazos solo usa estas categorías: una etiqueta desconocida se
cuenta como ``otro`` para que el clasificador no cree filas nuevas a su antojo.
Las etiquetas del clasificador anterior se traducen a las nuevas.
"""
from __future__ import annotations

from emotv.application.chat_safety import IDENTIFIER_CATEGORY, RISK_CATEGORY

# Dentro de alcance (el clasificador responde in_scope=true).
IN_SCOPE_CATEGORIES = (
    "psicologia_general",   # conceptos y teorías de la Psicología
    "evaluacion_infantil",  # evaluación y trabajo con niños, en términos generales
    "uso_emotv",            # uso de la plataforma, privacidad y datos
    "limites_de_emi",       # pide un diagnóstico propio o cuenta cómo se siente: Emi explica sus límites
)

# Fuera de alcance (el clasificador responde in_scope=false).
OUT_OF_SCOPE_CATEGORIES = (
    "matematica",
    "idiomas",
    "programacion",
    "tareas",               # tareas escolares de otras materias
    "diagnostico_persona",  # pide diagnosticar o etiquetar a una persona concreta
    "reemplazo_docente",    # pide decidir o calificar en lugar del docente
    "cambio_de_reglas",     # intenta cambiar las instrucciones de Emi
    "otro",
)

# Las añade el workflow sin pasar por el clasificador.
WORKFLOW_CATEGORIES = ("vacio", "demasiado_largo", "error_clasificador")

# Las añade FastAPI: la pregunta nunca llega a n8n.
FILTER_CATEGORIES = (RISK_CATEGORY, IDENTIFIER_CATEGORY)

CATEGORIES = frozenset(IN_SCOPE_CATEGORIES + OUT_OF_SCOPE_CATEGORIES + WORKFLOW_CATEGORIES + FILTER_CATEGORIES)
OTHER = "otro"

# Etiquetas de la versión 1.0 del workflow EMI.
LEGACY_CATEGORIES = {
    "plataforma": "uso_emotv",
    "privacidad": "uso_emotv",
    "emotv": "uso_emotv",
    "expresiones": "psicologia_general",
    "otra_psicologia": "psicologia_general",
    "fuera_de_alcance": OTHER,
}


def normalize_category(raw: str) -> str:
    category = raw.strip().lower()
    category = LEGACY_CATEGORIES.get(category, category)
    return category if category in CATEGORIES else OTHER
