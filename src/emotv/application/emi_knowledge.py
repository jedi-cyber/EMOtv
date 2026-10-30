"""Conocimiento verificado de EMOtv que viaja en el campo ``knowledge`` del webhook de Emi.

Se genera desde la base de datos (actividades y catálogo de expresiones) más
textos fijos del proyecto: posturas, flujo de uso, sesiones y
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

FLOW = """## Flujo de uso
1. Iniciar sesión con la cuenta asignada. Algunas cuentas deben cambiar su contraseña provisional al entrar.
2. Aceptar una vez el compromiso de confidencialidad vigente; sin aceptarlo no se inician sesiones.
3. Toda sesión empieza en el Analizador. Se elige un protocolo o «Sin protocolo (solo analizar)». Sin protocolo se indica con quién es la sesión: conmigo, un adulto o un niño o niña.
4. Antes de empezar se confirma una sola vez la autorización según el público. La sesión muestra un código (por ejemplo S-4F7K2Q) al empezar y al terminar, para anotarlo en el formato firmado.
5. Sin protocolo se permite la cámara del navegador, se lee la expresión en vivo y se registra cuando la lectura es estable; el resultado muestra la expresión, su confianza y textos educativos.
6. Se sugiere una actividad de varias posturas. La cámara verifica cada postura: el tiempo de un paso solo avanza mientras la postura es correcta. Si la persona no se ve completa, conviene alejarse un poco y centrarse.
7. Las sesiones anteriores se consultan en Mis sesiones."""

SESSIONS = """## Sesiones y autorizaciones
- No se registra a la persona evaluada: no se guarda nombre, DNI ni foto. Cada sesión lleva solo un código aleatorio.
- Una sesión propia o con un adulto se inicia confirmando que es propia o que se cuenta con la autorización firmada de la persona adulta. Con un niño o niña se confirma que su tutor autorizó por escrito, está presente y el niño aceptó participar.
- Acceden a una sesión quien la condujo y su docente. La administración no accede a contenidos.
- Quien condujo una sesión puede pedir su eliminación y su docente la ejecuta; queda un acta con el código, la fecha y los registros borrados, sin datos personales."""

PROTOCOLS = """## Protocolos
- Un protocolo es una receta guardada: qué aplicar en una sesión, para usarla cuando se quiera. Primero se indica si es para adultos o para niños.
- Contiene un nombre, un cuestionario previo opcional, imágenes en orden con sus segundos de exposición (1 a 120 s, hasta 30 imágenes) y un cuestionario posterior opcional. Un protocolo para niños solo admite imágenes leves y aprobadas.
- Los protocolos tienen versiones: uno usado en una sesión no se edita, se crea una versión nueva.
- Con protocolo, la sesión sigue sus pasos: cuestionario previo, calibración neutral, imágenes con captura y cuestionario posterior. Se detiene en cualquier momento si la persona, su tutor o quien conduce lo piden.
- Antes de cada captura se revisa la calidad: rostro visible, centrado, tamaño, iluminación e inclinación. Una captura con problemas se marca y no cuenta en las métricas.
- Quien conduce agrega marcadores (se distrajo, se rió, lloró, pidió parar o una nota). La persona ve las imágenes en su propia pantalla, sin resultados.
- Los cuestionarios y las imágenes abstractas solo se muestran y se registran: EMOtv no calcula puntajes ni interpreta las respuestas ni lo que la persona dice ver."""

METRICS = """## Línea de tiempo y métricas de la sesión
- La línea de tiempo ordena cuestionarios, imágenes, capturas, lo que la persona dijo ver y marcadores.
- Para cada imagen emocional se compara la primera captura de buena calidad con la expresión esperada de la imagen. Resumen: «En X de Y imágenes la expresión estimada coincidió con la esperada». Es una descripción, no una evaluación.
- Las estadísticas cuentan sesiones, nunca personas: no hay seguimiento por persona.
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
- Usuario: conduce sesiones desde el Analizador, arma sus cuestionarios y protocolos, redacta reportes y también analiza su propia expresión.
- Docente: tiene un grupo de usuarios, revisa y aprueba sus reportes, aprueba las imágenes que suben, ejecuta la eliminación de sesiones y también conduce sesiones propias.
- Administración: gestiona cuentas y grupos; no accede a sesiones ni resultados."""


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
    fixed = [INTRO, postures, FLOW, SESSIONS, PROTOCOLS, METRICS, REPORTS, LIMITATIONS, DATA, ROLES]
    for limit in (400, 320, 260, 200, 160, 120, 90, 60):
        # Los textos fijos van primero: si hay que recortar, solo se pierde contenido editable.
        text = "\n\n".join([*fixed, _activities_section(activities, limit),
                            _expressions_section(expressions, limit)])
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
