"""Conocimiento verificado de EMOtv que viaja en el campo ``knowledge`` del webhook de Emi.

Se genera desde la base de datos (actividades y catálogo de expresiones) más
textos fijos del proyecto: posturas, flujo de uso, datos guardados y roles. No
incluye datos de ningún usuario: ni sesiones, ni resultados, ni nombres, ni
identificadores (tampoco quién revisó un texto).

El workflow EMI corta lo que exceda ``MAX_KNOWLEDGE_CHARS``; si el contenido
editado por administración crece, los textos de expresiones y actividades se
acortan para no superar ese límite.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable

from emotv.domain.activity import Activity
from emotv.domain.expression_info import ExpressionInfo, ReviewStatus
from emotv.domain.posture_id import PostureId

logger = logging.getLogger(__name__)

MAX_KNOWLEDGE_CHARS = 12_000
# Margen bajo el límite del workflow.
TARGET_CHARS = 11_500
# Respaldo si varios procesos no comparten la invalidación en memoria.
CACHE_SECONDS = 600.0

POSTURES: dict[PostureId, tuple[str, str]] = {
    PostureId.ARMS_UP: ("Brazos arriba", "Levanta ambos brazos extendidos por encima de los hombros."),
    PostureId.ARMS_OPEN: ("Brazos abiertos", "Extiende ambos brazos hacia los lados, a la altura de los hombros."),
    PostureId.ARMS_FORWARD: ("Brazos al frente", "Extiende ambos brazos al frente, a la altura de los hombros."),
    PostureId.HANDS_ON_HIPS: ("Manos en las caderas", "Apoya las manos en las caderas con los codos hacia afuera."),
    PostureId.SQUAT: ("Sentadilla suave", "Flexiona ambas rodillas suavemente, sin forzarte, con el cuerpo "
                                          "completo visible de hombros a tobillos."),
}

INTRO = """# Conocimiento de EMOtv
EMOtv es un proyecto formativo de la Facultad de Psicología de la UNHEVAL. Estima la expresión facial visible con la cámara, muestra información educativa sobre esa expresión y propone una actividad guiada de posturas. La estimación no indica lo que una persona siente, no es diagnóstico ni evaluación psicológica y no sustituye a un profesional. Las actividades son actividad guiada, no terapia."""

FLOW = """## Flujo de uso
1. Iniciar sesión con la cuenta asignada. Algunas cuentas deben cambiar su contraseña provisional al entrar.
2. Aceptar la política de consentimiento vigente en la página Consentimiento; se puede revocar en cualquier momento y entonces no se inicia ningún análisis nuevo.
3. En Analizador facial, permitir la cámara del navegador y pulsar «Reconocer mi expresión». Se ve la lectura en vivo; cuando es estable, el estudiante pulsa «Registrar esta expresión».
4. La pantalla de resultado muestra la expresión registrada, su confianza y textos educativos, con la limitación de que la imagen no determina el estado emocional.
5. Se sugiere una actividad de varias posturas; se puede elegir otra de la lista, finalizar sin actividad o analizar otra expresión.
6. Durante la actividad la cámara verifica cada postura: el tiempo de un paso solo avanza mientras la postura es correcta. Si la persona no se ve completa, conviene alejarse un poco y centrarse. La web indica paso, repetición, postura esperada y tiempo restante, y puede leer las instrucciones en voz alta.
7. Las sesiones anteriores se consultan en Sesiones."""

DATA = """## Qué se guarda y qué no
- No se guardan fotografías, video ni los puntos del cuerpo. Cada imagen se analiza en memoria y se descarta.
- Se guarda, asociado a la cuenta: la expresión registrada y su confianza, la actividad, los pasos completados, su resultado y su duración.
- Las preguntas a Emi y sus respuestas se guardan hasta 90 días. A Emi solo llegan la pregunta y la conversación; nunca nombres, correos, cuentas ni resultados.
- En las pruebas con voluntarios, los datos de la cuenta de prueba se eliminan como máximo a los 30 días."""

ROLES = """## Roles
- Estudiante: analiza su expresión, realiza actividades, consulta sus sesiones y gestiona su consentimiento.
- Psicólogo: consulta las sesiones de los estudiantes que administración le asignó; no realiza análisis en nombre de otros.
- Administrador: gestiona usuarios, actividades, textos del catálogo de expresiones, recomendaciones y políticas de consentimiento."""


def shorten(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    sentence = cut.rfind(". ")
    if sentence >= limit * 0.6:
        return cut[:sentence + 1]
    return cut[:cut.rfind(" ")].rstrip(",;:") + "…"


def _activities_section(activities: Iterable[Activity], limit: int) -> str:
    lines = ["## Actividades disponibles"]
    for activity in activities:
        repetitions = f", {activity.repetitions} repeticiones" if activity.repetitions > 1 else ""
        lines.append(f"- {shorten(activity.name, 80)}{repetitions}: {shorten(activity.description, limit)}")
        for number, step in enumerate(activity.steps, start=1):
            name = POSTURES.get(PostureId(step.posture), (str(step.posture), ""))[0]
            instruction = "" if step.instruction == activity.description else f": {shorten(step.instruction, limit)}"
            lines.append(f"  {number}. {name}, {step.duration_seconds:g} s{instruction}")
    return "\n".join(lines)


def _expressions_section(expressions: Iterable[ExpressionInfo], limit: int) -> str:
    lines = ["## Expresiones faciales (textos del catálogo)"]
    for item in expressions:
        pending = "" if item.review_status is ReviewStatus.REVIEWED else " (texto pendiente de revisión)"
        lines.append(f"### {item.label_es}{pending}")
        lines.append(f"- Qué es: {shorten(item.what_it_is, limit)}")
        lines.append(f"- Por qué suele presentarse: {shorten(item.why_it_occurs, limit)}")
        lines.append(f"- Cómo se reconoce: {shorten(item.facial_cues, limit)}")
    return "\n".join(lines)


def build_knowledge(activities: Iterable[Activity], expressions: Iterable[ExpressionInfo]) -> str:
    activities, expressions = tuple(activities), tuple(expressions)
    postures = "## Posturas\n" + "\n".join(f"- {name}: {instruction}" for name, instruction in POSTURES.values())
    fixed = [INTRO, postures, FLOW, DATA, ROLES]
    for limit in (400, 320, 260, 200, 160, 120, 90, 60):
        text = "\n\n".join([*fixed[:2], _activities_section(activities, limit),
                            _expressions_section(expressions, limit), *fixed[2:]])
        if len(text) <= TARGET_CHARS:
            return text
    marker = "\n[Conocimiento recortado por longitud]"
    return text[:TARGET_CHARS - len(marker)].rsplit("\n", 1)[0] + marker


class EmiKnowledge:
    """Caché en memoria del conocimiento; se invalida al editar actividades o el catálogo."""

    def __init__(
        self,
        activities: Callable[[], Iterable[Activity]],
        expressions: Callable[[], Iterable[ExpressionInfo]],
        cache_seconds: float = CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._activities = activities
        self._expressions = expressions
        self._cache_seconds = cache_seconds
        self._clock = clock
        self._text: str | None = None
        self._built_at = 0.0
        self._lock = threading.Lock()

    def invalidate(self) -> None:
        with self._lock:
            self._text = None

    def get(self) -> str:
        with self._lock:
            if self._text is not None and self._clock() - self._built_at < self._cache_seconds:
                return self._text
            try:
                text = build_knowledge(self._activities(), self._expressions())
            except Exception:  # la base puede fallar; Emi sigue respondiendo
                logger.exception("No se pudo regenerar el conocimiento de Emi; se usa el anterior")
                return self._text or ""
            self._text, self._built_at = text, self._clock()
            logger.info("Conocimiento de Emi regenerado: %d caracteres (límite %d)", len(text), MAX_KNOWLEDGE_CHARS)
            return text
