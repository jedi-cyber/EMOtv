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


class ProtocolKind(str, Enum):
    """Práctica: cuestionarios e imágenes con su tiempo. Examen simulado: EMOtv
    registra todo el examen; no tiene pasos ni cuestionarios que configurar."""

    PRACTICE = "practice"
    EXAM = "exam"


class StepKind(str, Enum):
    """Estímulo: una imagen con su captura automática. Práctica: se pide una
    expresión y la persona ve una señal que crece al acercarse a ella."""

    STIMULUS = "stimulus"
    PRACTICE = "practice"


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
    """

    stimulus_id: str | None
    exposure_seconds: int
    capture_after_seconds: int
    record_verbal_response: bool = False
    shown_before_analyzer: bool = False
    kind: StepKind | str = StepKind.STIMULUS
    target_expression: str | None = None
    hold_seconds: int | None = None

    def __post_init__(self) -> None:
        kind = StepKind(self.kind)
        object.__setattr__(self, "kind", kind)
        stimulus_id = self.stimulus_id.strip() if isinstance(self.stimulus_id, str) else self.stimulus_id
        if kind is StepKind.STIMULUS and not stimulus_id:
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
            if self.target_expression is not None or self.hold_seconds is not None:
                raise ValueError("Un paso de estímulo no tiene expresión pedida ni tiempo de sostén")
            return
        if self.target_expression not in PRACTICE_TARGETS:
            raise ValueError("Una práctica indica la expresión que se pide")
        if isinstance(self.hold_seconds, bool) or not isinstance(self.hold_seconds, int):
            raise TypeError("hold_seconds debe ser un entero de segundos")
        if not 1 <= self.hold_seconds <= MAX_HOLD_SECONDS:
            raise ValueError(f"La expresión se sostiene entre 1 y {MAX_HOLD_SECONDS} segundos")
        if self.hold_seconds >= self.exposure_seconds:
            raise ValueError("El tiempo máximo de la práctica es mayor que el tiempo de sostén")
        if self.capture_after_seconds != 0:
            raise ValueError("Una práctica no tiene captura automática")
        if self.record_verbal_response or self.shown_before_analyzer:
            raise ValueError("Una práctica no registra respuesta verbal ni va antes del analizador")

    @classmethod
    def practice(cls, target_expression: str, hold_seconds: int, max_seconds: int,
                 illustration_id: str | None = None) -> ProtocolStep:
        return cls(illustration_id, max_seconds, 0, kind=StepKind.PRACTICE,
                   target_expression=target_expression, hold_seconds=hold_seconds)

    @property
    def is_practice(self) -> bool:
        return self.kind is StepKind.PRACTICE


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
        steps = tuple(self.steps)
        object.__setattr__(self, "steps", steps)
        for name in ("pre_questionnaire_id", "post_questionnaire_id"):
            object.__setattr__(self, name, (getattr(self, name) or "").strip() or None)
        if kind is ProtocolKind.EXAM:
            if steps or self.pre_questionnaire_id or self.post_questionnaire_id:
                raise ValueError("Un examen no tiene estímulos ni cuestionarios que configurar")
            if self.for_children:
                raise ValueError("Un examen simulado es solo para personas adultas")
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
