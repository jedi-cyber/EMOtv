"""Conocimiento verificado de EMOtv que viaja en el campo ``knowledge`` del webhook de Emi.

Se genera desde la base de datos (actividades y catálogo de expresiones) más
textos fijos del proyecto: la guía de uso (``user_guide``), posturas, sesiones y
autorizaciones, protocolos, métricas de la sesión, estados del reporte,
limitaciones del reconocimiento facial, datos guardados y roles. No incluye
datos de ningún usuario ni persona evaluada: ni sesiones, ni reportes, ni
resultados, ni nombres, ni identificadores (tampoco quién revisó un texto).

El workflow EMI corta lo que exceda ``MAX_KNOWLEDGE_CHARS``; si el contenido
editado por administración crece, los textos de expresiones y actividades se
acortan para no superar ese límite.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable

from emotv.application.user_guide import guide_knowledge
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
EMOtv es una herramienta de apoyo de la Facultad de Psicología de la UNHEVAL para usuarios y docentes, que la aplican con personas adultas o con niños. Estima la expresión facial visible con la cámara, permite aplicar protocolos (cuestionarios e imágenes) durante una sesión, muestra una línea de tiempo con métricas descriptivas y un reporte que revisa el docente, y propone actividades guiadas de posturas. La estimación no indica lo que una persona siente, no es diagnóstico ni evaluación psicológica y no sustituye a un profesional. Las actividades son actividad guiada, no terapia. Emi responde a usuarios y docentes; las personas evaluadas no tienen cuenta ni usan Emi."""

# Cómo hacer cada tarea está en la guía de uso; aquí quedan las reglas.
SESSIONS = """## Sesiones y autorizaciones
- No se registra a la persona evaluada: no se guarda nombre, DNI ni foto. Cada sesión lleva solo un código aleatorio.
- Sin la confirmación de la autorización no hay sesión: la firma de la persona adulta o, con un niño o niña, su tutor autorizó por escrito, está presente y el niño aceptó.
- Acceden a una sesión quien la condujo y su docente. La administración no accede a contenidos.
- El acta de una eliminación lleva el código, la fecha y los registros borrados, sin datos personales."""

PROTOCOLS = """## Protocolos
- Un protocolo es una receta guardada para adultos o para niños: cuestionario previo opcional, hasta 30 pasos en orden (1 a 120 s cada uno) y cuestionario posterior opcional. Con niños solo admite imágenes leves y aprobadas.
- Pasos: una imagen con captura de la expresión estimada; «¿Qué emoción es?», donde la persona elige una emoción sin que se analice la cámara; un ejercicio de práctica con una señal de 0 a 1 que crece al acercarse a la expresión pedida; y «Haz la misma cara», una práctica en la que la imagen es el modelo.
- Un protocolo usado en una sesión no se edita: se crea una versión nueva.
- Antes de cada captura se revisa la calidad (rostro visible, centrado, tamaño, luz e inclinación). Una captura con problemas no cuenta en las métricas.
- La pantalla de la persona no muestra resultados, etiquetas ni probabilidades. EMOtv no calcula puntajes ni interpreta las respuestas."""

METRICS = """## Línea de tiempo y métricas de la sesión
- La línea de tiempo ordena cuestionarios, imágenes, capturas, lo que la persona dijo ver y marcadores.
- Para cada imagen emocional se compara la primera captura de buena calidad con la expresión esperada de la imagen. Resumen: «En X de Y imágenes la expresión estimada coincidió con la esperada». Es una descripción, no una evaluación.
- Una sesión breve con imágenes abstractas no permite concluir nada sobre la persona."""

REPORTS = """## Reporte de la sesión
- Lo redacta quien condujo la sesión y lo revisa su docente, por secciones.
- Estados: borrador, enviado a revisión, con observaciones (el docente lo devolvió) y aprobado. El reporte de un docente se cierra sin revisión.
- Un reporte aprobado no se edita: se crea una versión nueva, que vuelve a revisión. Solo se imprime un reporte aprobado y cada impresión queda registrada.
- Todo reporte lleva el aviso de que las expresiones son estimaciones de apoyo de un modelo automático."""

LIMITATIONS = """## Limitaciones del reconocimiento facial
- El modelo estima la expresión visible del rostro; una expresión no equivale a lo que la persona siente.
- Influyen la iluminación, el ángulo, la distancia, los lentes, la mascarilla, el cabello y el movimiento.
- Las expresiones varían entre personas, culturas y edades; con niños la estimación puede ser menos precisa.
- Una persona puede contener o actuar una expresión, y una captura dura un instante.
- El modelo puede equivocarse: los resultados son de apoyo y los interpreta un profesional, nunca el sistema."""

DATA = """## Qué se guarda y qué no
- No se guardan fotografías, video ni los puntos del cuerpo. Cada imagen se analiza en memoria y se descarta. Las únicas imágenes guardadas son los estímulos subidos por docentes o administración.
- Se guardan la expresión estimada y su confianza, las actividades, las respuestas a cuestionarios, los marcadores y los reportes. Notas, respuestas, comentarios y textos de reportes se guardan cifrados.
- Las preguntas a Emi y sus respuestas se guardan hasta 90 días y cada persona puede borrar su conversación. A Emi nunca llegan datos de sesiones, reportes ni resultados. Emi rechaza mensajes con DNI, correos o teléfonos; no se deben escribir nombres ni datos de niños o familias."""

ROLES = """## Roles
- Usuario: conduce sesiones, arma cuestionarios y protocolos y redacta reportes; también analiza su propia expresión.
- Docente: supervisa a su grupo sin estar en cada sesión y revisa después reportes, imágenes y eliminaciones. Sus sesiones propias son de demostración.
- Administración: gestiona cuentas, grupos y estímulos institucionales; no accede a sesiones ni resultados."""


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
        names = [POSTURES.get(PostureId(step.posture), (str(step.posture), ""))[0] for step in activity.steps]
        if limit < 160:
            # Con poco espacio, los pasos van en una línea, sin sus instrucciones.
            lines.append("  Pasos: " + ", ".join(f"{name} {step.duration_seconds:g} s"
                                                for name, step in zip(names, activity.steps)))
            continue
        for number, (name, step) in enumerate(zip(names, activity.steps), start=1):
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


def _without_activities(intro: str) -> str:
    """Presentación sin las actividades corporales, que están congeladas."""
    return intro.replace(", y propone actividades guiadas de posturas", "").replace(
        " Las actividades son actividad guiada, no terapia.", "")


def build_knowledge(activities: Iterable[Activity], expressions: Iterable[ExpressionInfo],
                    activities_enabled: bool = True) -> str:
    activities, expressions = tuple(activities), tuple(expressions)
    guide = guide_knowledge()
    if activities_enabled:
        postures = ("## Posturas (la cámara verifica cada una)\n"
                    + "\n".join(f"- {name}: {instruction}" for name, instruction in POSTURES.values()))
        fixed = [INTRO, guide, postures, SESSIONS, PROTOCOLS, METRICS, REPORTS, LIMITATIONS, DATA, ROLES]
    else:
        fixed = [_without_activities(INTRO), guide, SESSIONS, PROTOCOLS, METRICS, REPORTS, LIMITATIONS, DATA, ROLES]
    for limit in (400, 320, 260, 200, 160, 120, 90, 60):
        # Los textos fijos van primero: si hay que recortar, solo se pierde contenido editable.
        sections = [_activities_section(activities, limit)] if activities_enabled else []
        text = "\n\n".join([*fixed, *sections, _expressions_section(expressions, limit)])
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
        activities_enabled: bool = True,
    ) -> None:
        self._activities = activities
        # Con las actividades congeladas, Emi no las describe ni las sugiere.
        self._activities_enabled = activities_enabled
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
                text = build_knowledge(self._activities() if self._activities_enabled else (),
                                       self._expressions(), self._activities_enabled)
            except Exception:  # la base puede fallar; Emi sigue respondiendo
                logger.exception("No se pudo regenerar el conocimiento de Emi; se usa el anterior")
                return self._text or ""
            self._text, self._built_at = text, self._clock()
            logger.info("Conocimiento de Emi regenerado: %d caracteres (límite %d)", len(text), MAX_KNOWLEDGE_CHARS)
            return text
