from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from emotv.domain.expression_info import EXPRESSION_KEYS

MAX_EXPOSURE_SECONDS = 120
MAX_STEPS = 30
MAX_HOLD_SECONDS = 10
# Expresiones que se pueden pedir en una práctica: todo el catálogo. Quien arma
# el protocolo decide; la validación con adultos muestra cuáles se registran mejor
# (docs/expression-practice.md, §14.1).
PRACTICE_TARGETS = EXPRESSION_KEYS
# Opciones de un paso de reconocimiento: la correcta y las distractoras.
MIN_RECOGNITION_OPTIONS = 2
MAX_RECOGNITION_OPTIONS = 4
DEFAULT_RECOGNITION_OPTIONS = 3
# Historia corta de una situación («A Lucía se le cayó su helado»).
MAX_SITUATION_CHARS = 200
# Modo accesible: la pausa tras cada ejercicio o reconocimiento dura esto veces más.
ACCESSIBLE_PAUSE_FACTOR = 2
# Sin límite de tiempo, un reconocimiento o un ejercicio termina al responder, al
# lograrlo o cuando quien conduce lo salta; este tope solo evita una sesión colgada.
NO_TIME_LIMIT_SECONDS = 1800
# «Esperar a quien conduce»: la pausa dura hasta que pulsa «Seguir», con este tope.
WAIT_PAUSE_SECONDS = 600


class PauseMode(str, Enum):
    """Pausa tras cada reconocimiento o ejercicio: la normal, el doble o hasta
    que quien conduce pulse «Seguir»."""

    NORMAL = "normal"
    LONG = "long"
    WAIT = "wait"


@dataclass(frozen=True, slots=True)
class ProtocolSupports:
    """Apoyos de la pantalla de la persona, por protocolo. Cambian la
    presentación y el ritmo; no cambian lo que se registra.

    - pictograms: un pictograma junto al nombre de cada emoción.
    - large_controls: botones y letra más grandes, sin animaciones.
    - read_aloud: la consigna se lee en voz alta al empezar cada paso.
    - no_time_limit: el reconocimiento y la práctica no vencen por tiempo.
    - pause: normal, larga (el doble) o hasta que quien conduce pulse «Seguir».
    """

    pictograms: bool = False
    large_controls: bool = False
    read_aloud: bool = False
    no_time_limit: bool = False
    pause: PauseMode | str = PauseMode.NORMAL

    def __post_init__(self) -> None:
        for name in ("pictograms", "large_controls", "read_aloud", "no_time_limit"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} debe ser verdadero o falso")
        object.__setattr__(self, "pause", PauseMode(self.pause))

    @property
    def any(self) -> bool:
        return self != NO_SUPPORTS


NO_SUPPORTS = ProtocolSupports()
# El modo accesible de siempre: pictogramas, botones grandes y pausa larga.
ACCESSIBLE_PRESET = ProtocolSupports(pictograms=True, large_controls=True, pause=PauseMode.LONG)


class ProtocolKind(str, Enum):
    """Práctica: cuestionarios e imágenes con su tiempo. Examen simulado: EMOtv
    registra todo el examen; no tiene pasos ni cuestionarios que configurar."""

    PRACTICE = "practice"
    EXAM = "exam"


class StepKind(str, Enum):
    """Estímulo: una imagen con su captura automática. Práctica: se pide una
    expresión y la persona ve una señal que crece al acercarse a ella.
    Reconocimiento: se muestra una imagen emocional y la persona elige qué
    emoción es entre unas pocas opciones. Dibujo: la persona dibuja una cara
    en su pantalla y señala qué emoción quiso representar; el dibujo no sale
    del dispositivo ni se interpreta."""

    STIMULUS = "stimulus"
    PRACTICE = "practice"
    RECOGNITION = "recognition"
    DRAWING = "drawing"


@dataclass(frozen=True, slots=True)
class ProtocolStep:
    """Un paso de la secuencia.

    En un estímulo, capture_after_seconds es el tiempo hasta la captura
    automática de la expresión estimada, dentro de la exposición.
    record_verbal_response solo aplica a imágenes abstractas: se registra lo que
    la persona dice ver, sin interpretarlo. shown_before_analyzer (solo
    abstractas) la muestra antes de la calibración, sin capturas.

    En una práctica, target_expression es la expresión pedida, hold_seconds el
    tiempo que debe sostenerse y exposure_seconds el tiempo máximo. stimulus_id
    es opcional: una ilustración de apoyo. No hay captura automática, respuesta
    verbal ni paso antes del analizador (la práctica necesita la cámara).
    Con imitate, la ilustración es un modelo: la persona lee «Haz la misma
    cara» y target_expression es la expresión esperada de esa imagen, que copia
    el servicio de protocolos.

    En un reconocimiento, stimulus_id es una imagen emocional del banco y
    target_expression su expresión esperada: la respuesta correcta, que copia
    el servicio de protocolos (quien arma el protocolo no la escribe).
    option_count es cuántas opciones se muestran y exposure_seconds el tiempo
    máximo para responder. No analiza la cámara. situation, opcional, es una
    historia corta que acompaña a la ilustración: con ella la pregunta es
    «¿Qué emoción muestra la cara?». La respuesta sigue siendo la expresión de la imagen.

    En un dibujo no hay estímulo, expresión pedida ni opciones que configurar:
    exposure_seconds es el tiempo máximo. Solo se registra la emoción que la
    persona señaló y los tiempos, nunca el dibujo. No analiza la cámara.
    """

    stimulus_id: str | None
    exposure_seconds: int
    capture_after_seconds: int
    record_verbal_response: bool = False
    shown_before_analyzer: bool = False
    kind: StepKind | str = StepKind.STIMULUS
    target_expression: str | None = None
    hold_seconds: int | None = None
    option_count: int | None = None
    situation: str | None = None
    imitate: bool = False

    def __post_init__(self) -> None:
        kind = StepKind(self.kind)
        object.__setattr__(self, "kind", kind)
        if not isinstance(self.imitate, bool):
            raise TypeError("imitate debe ser verdadero o falso")
        if self.imitate and kind is not StepKind.PRACTICE:
            raise ValueError("Solo un ejercicio de práctica imita un modelo")
        if self.imitate and not (isinstance(self.stimulus_id, str) and self.stimulus_id.strip()):
            raise ValueError("«Haz la misma cara» necesita la imagen del modelo")
        if self.situation is not None:
            if not isinstance(self.situation, str):
                raise TypeError("situation debe ser un texto")
            situation = " ".join(self.situation.split()) or None
            if situation is not None and kind is not StepKind.RECOGNITION:
                raise ValueError("Solo un paso «¿Qué emoción es?» lleva una situación")
            if situation is not None and len(situation) > MAX_SITUATION_CHARS:
                raise ValueError(f"La situación tiene como máximo {MAX_SITUATION_CHARS} caracteres")
            object.__setattr__(self, "situation", situation)
        stimulus_id = self.stimulus_id.strip() if isinstance(self.stimulus_id, str) else self.stimulus_id
        if kind in (StepKind.STIMULUS, StepKind.RECOGNITION) and not stimulus_id:
            raise ValueError("Cada paso indica un estímulo")
        if stimulus_id is not None and not isinstance(stimulus_id, str):
            raise TypeError("stimulus_id debe ser un texto")
        object.__setattr__(self, "stimulus_id", stimulus_id or None)
        for name in ("exposure_seconds", "capture_after_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} debe ser un entero de segundos")
        if not 1 <= self.exposure_seconds <= MAX_EXPOSURE_SECONDS:
            raise ValueError(f"La exposición dura entre 1 y {MAX_EXPOSURE_SECONDS} segundos")
        if not 0 <= self.capture_after_seconds <= self.exposure_seconds:
            raise ValueError("La captura automática ocurre durante la exposición")
        if kind is StepKind.STIMULUS:
            if self.target_expression is not None or self.hold_seconds is not None or self.option_count is not None:
                raise ValueError("Un paso de estímulo no tiene expresión pedida ni tiempo de sostén")
            return
        if self.record_verbal_response or self.shown_before_analyzer:
            raise ValueError("Una práctica o un reconocimiento no registra respuesta verbal ni va antes "
                             "del analizador")
        if self.capture_after_seconds != 0:
            raise ValueError("Una práctica o un reconocimiento no tiene captura automática")
        if kind is StepKind.DRAWING:
            if (stimulus_id is not None or self.target_expression is not None or self.hold_seconds is not None
                    or self.option_count is not None):
                raise ValueError("Un dibujo no tiene imagen, expresión pedida, tiempo de sostén ni opciones")
            return
        if kind is StepKind.RECOGNITION:
            if self.target_expression is not None and self.target_expression not in EXPRESSION_KEYS:
                raise ValueError("La expresión de la imagen no es válida")
            if self.hold_seconds is not None:
                raise ValueError("Un reconocimiento no tiene tiempo de sostén")
            if isinstance(self.option_count, bool) or not isinstance(self.option_count, int):
                raise TypeError("option_count debe ser un entero")
            if not MIN_RECOGNITION_OPTIONS <= self.option_count <= MAX_RECOGNITION_OPTIONS:
                raise ValueError(f"Un reconocimiento muestra entre {MIN_RECOGNITION_OPTIONS} y "
                                 f"{MAX_RECOGNITION_OPTIONS} opciones")
            return
        if self.option_count is not None:
            raise ValueError("Una práctica no tiene opciones")
        if self.target_expression not in PRACTICE_TARGETS:
            raise ValueError("Una práctica indica la expresión que se pide")
        if isinstance(self.hold_seconds, bool) or not isinstance(self.hold_seconds, int):
            raise TypeError("hold_seconds debe ser un entero de segundos")
        if not 1 <= self.hold_seconds <= MAX_HOLD_SECONDS:
            raise ValueError(f"La expresión se sostiene entre 1 y {MAX_HOLD_SECONDS} segundos")
        if self.hold_seconds >= self.exposure_seconds:
            raise ValueError("El tiempo máximo de la práctica es mayor que el tiempo de sostén")

    @classmethod
    def practice(cls, target_expression: str, hold_seconds: int, max_seconds: int,
                 illustration_id: str | None = None, imitate: bool = False) -> ProtocolStep:
        return cls(illustration_id, max_seconds, 0, kind=StepKind.PRACTICE,
                   target_expression=target_expression, hold_seconds=hold_seconds, imitate=imitate)

    @classmethod
    def recognition(cls, stimulus_id: str, max_seconds: int, option_count: int = DEFAULT_RECOGNITION_OPTIONS,
                    target_expression: str | None = None, situation: str | None = None) -> ProtocolStep:
        return cls(stimulus_id, max_seconds, 0, kind=StepKind.RECOGNITION, target_expression=target_expression,
                   option_count=option_count, situation=situation)

    @classmethod
    def drawing(cls, max_seconds: int) -> ProtocolStep:
        return cls(None, max_seconds, 0, kind=StepKind.DRAWING)

    @property
    def is_drawing(self) -> bool:
        return self.kind is StepKind.DRAWING

    @property
    def is_timed(self) -> bool:
        """Termina al lograrlo, al responder o al vencer su tiempo máximo, con pausa
        después: una práctica, un reconocimiento o un dibujo."""
        return self.kind in (StepKind.PRACTICE, StepKind.RECOGNITION, StepKind.DRAWING)

    @property
    def is_practice(self) -> bool:
        return self.kind is StepKind.PRACTICE

    @property
    def is_recognition(self) -> bool:
        return self.kind is StepKind.RECOGNITION

    @property
    def uses_camera(self) -> bool:
        """Una imagen con captura o un ejercicio de práctica; un reconocimiento o un dibujo no."""
        return self.kind in (StepKind.STIMULUS, StepKind.PRACTICE)


@dataclass(frozen=True, slots=True)
class Protocol:
    """Una versión de un protocolo: una receta guardada de qué aplicar en una
    sesión. Las versiones de un mismo protocolo comparten family_id; la vigente
    es la que no tiene superseded_at.

    kind distingue una práctica de un examen simulado. Un examen es solo para
    adultos y no tiene pasos ni cuestionarios.

    for_children fija el público de las sesiones que lo aplican. No necesita
    aprobación del docente (approved_at queda de versiones anteriores). Uno
    usado en una sesión no se edita: se crea una versión nueva.

    supports son los apoyos de la pantalla de la persona (ProtocolSupports).
    accessible=True sin supports equivale al preajuste de siempre
    (ACCESSIBLE_PRESET); después, accessible indica si hay algún apoyo.

    shared_with_group: el docente lo ofrece como plantilla a los usuarios de su
    grupo, que lo copian como protocolo propio (como con los cuestionarios).
    """

    id: str
    family_id: str
    version: int
    owner_user_id: str
    name: str
    description: str
    for_children: bool
    created_at: datetime
    steps: tuple[ProtocolStep, ...] = field(default_factory=tuple)
    pre_questionnaire_id: str | None = None
    post_questionnaire_id: str | None = None
    approved_at: datetime | None = None
    approved_by_user_id: str | None = None
    superseded_at: datetime | None = None
    kind: ProtocolKind | str = ProtocolKind.PRACTICE
    accessible: bool = False
    shared_with_group: bool = False
    supports: ProtocolSupports | None = None

    def __post_init__(self) -> None:
        for name in ("id", "family_id", "owner_user_id", "name"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
            object.__setattr__(self, name, value.strip())
        object.__setattr__(self, "description", (self.description or "").strip())
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version debe ser un entero positivo")
        kind = ProtocolKind(self.kind)
        object.__setattr__(self, "kind", kind)
        supports = self.supports if self.supports is not None else (
            ACCESSIBLE_PRESET if self.accessible else NO_SUPPORTS)
        if not isinstance(supports, ProtocolSupports):
            raise ValueError("supports debe ser un ProtocolSupports")
        object.__setattr__(self, "supports", supports)
        object.__setattr__(self, "accessible", supports.any)
        steps = tuple(self.steps)
        object.__setattr__(self, "steps", steps)
        for name in ("pre_questionnaire_id", "post_questionnaire_id"):
            object.__setattr__(self, name, (getattr(self, name) or "").strip() or None)
        if kind is ProtocolKind.EXAM:
            if steps or self.pre_questionnaire_id or self.post_questionnaire_id:
                raise ValueError("Un examen no tiene estímulos ni cuestionarios que configurar")
            if self.for_children:
                raise ValueError("Un examen simulado es solo para personas adultas")
            if self.accessible or self.shared_with_group:
                raise ValueError("Un examen simulado no tiene modo accesible ni apoyos, ni se comparte como plantilla")
        elif not 1 <= len(steps) <= MAX_STEPS:
            raise ValueError(f"Un protocolo tiene entre 1 y {MAX_STEPS} estímulos")
        if (self.approved_at is None) != (self.approved_by_user_id is None):
            raise ValueError("La aprobación requiere fecha y quien aprueba")
        for name in ("created_at", "approved_at", "superseded_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")

    @property
    def approved(self) -> bool:
        return self.approved_at is not None

    @property
    def current(self) -> bool:
        return self.superseded_at is None

    @property
    def uses_camera(self) -> bool:
        """Si la sesión necesita la cámara: un examen, o algún paso con imagen y
        captura o un ejercicio de práctica. Un protocolo solo de reconocimiento se
        aplica sin cámara, sin calibración y sin enviar cuadros."""
        return self.kind is ProtocolKind.EXAM or any(step.uses_camera for step in self.steps)
