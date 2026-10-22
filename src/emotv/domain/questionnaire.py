"""Cuestionarios creados por quien conduce la sesión.

EMOtv solo los presenta y registra las respuestas tal como se dieron: no valida
el cuestionario como instrumento, no calcula puntajes ni interpreta respuestas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

MAX_QUESTIONS = 40
MAX_OPTIONS = 10
MAX_TEXT_ANSWER = 500
FACES = 5  # figuras de la escala de caritas dibujadas para EMOtv


class QuestionKind(str, Enum):
    SCALE = "scale"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_TEXT = "short_text"
    FACES = "faces"


class ResponseMoment(str, Enum):
    PRE = "pre"    # antes de iniciar el analizador
    POST = "post"  # después, si el protocolo lo indica


class EntryMode(str, Enum):
    PARTICIPANT = "participant"  # respondió quien participa, en la vista de participante
    CONDUCTOR = "conductor"      # quien conduce la sesión registró las respuestas a mano


def _text(value: object, name: str, limit: int, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{name} debe ser texto")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} es obligatorio")
    if len(value) > limit:
        raise ValueError(f"{name} supera los {limit} caracteres")
    return value


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    kind: QuestionKind | str
    text: str
    required: bool = False
    options: tuple[str, ...] = ()
    scale_points: int | None = None
    # Etiquetas de los extremos: obligatorias en la escala, opcionales en caritas.
    min_label: str | None = None
    max_label: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _text(self.id, "id", 36))
        kind = QuestionKind(self.kind)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "text", _text(self.text, "El texto de la pregunta", 300))
        if not isinstance(self.required, bool):
            raise TypeError("required debe ser verdadero o falso")
        options = tuple(_text(item, "Cada opción", 120) for item in self.options)
        min_label = _text(self.min_label, "La etiqueta del extremo inferior", 60, required=False) or None
        max_label = _text(self.max_label, "La etiqueta del extremo superior", 60, required=False) or None
        if kind in (QuestionKind.SINGLE_CHOICE, QuestionKind.MULTIPLE_CHOICE):
            if not 2 <= len(options) <= MAX_OPTIONS:
                raise ValueError(f"Una pregunta de opciones tiene entre 2 y {MAX_OPTIONS} opciones")
            if len(set(options)) != len(options):
                raise ValueError("Las opciones de una pregunta no se repiten")
        elif options:
            raise ValueError("Solo las preguntas de opciones tienen opciones")
        if kind is QuestionKind.SCALE:
            points = self.scale_points
            if isinstance(points, bool) or not isinstance(points, int) or not 2 <= points <= 7:
                raise ValueError("Una escala tiene de 2 a 7 puntos")
            if min_label is None or max_label is None:
                raise ValueError("Una escala indica las etiquetas de sus extremos")
        elif self.scale_points is not None:
            raise ValueError("Solo las escalas indican cantidad de puntos")
        if kind not in (QuestionKind.SCALE, QuestionKind.FACES) and (min_label or max_label):
            raise ValueError("Solo las escalas y las caritas tienen etiquetas en los extremos")
        object.__setattr__(self, "options", options)
        object.__setattr__(self, "min_label", min_label)
        object.__setattr__(self, "max_label", max_label)

    def normalize(self, value: Any) -> Any:
        """La respuesta tal como se dio, validada según el tipo; None si quedó vacía."""
        if value is None or value == "" or value == []:
            return None
        kind = self.kind
        if kind in (QuestionKind.SCALE, QuestionKind.FACES):
            top = self.scale_points if kind is QuestionKind.SCALE else FACES
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= top:
                raise ValueError(f"«{self.text}»: elige una posición entre 1 y {top}")
            return value
        if kind is QuestionKind.SINGLE_CHOICE:
            if value not in self.options:
                raise ValueError(f"«{self.text}»: elige una de las opciones")
            return value
        if kind is QuestionKind.MULTIPLE_CHOICE:
            if not isinstance(value, list) or any(item not in self.options for item in value):
                raise ValueError(f"«{self.text}»: elige entre las opciones")
            # Se conserva el orden de las opciones; sin repeticiones.
            return [item for item in self.options if item in value]
        if not isinstance(value, str):
            raise ValueError(f"«{self.text}»: la respuesta es texto")
        text = value.strip()
        if len(text) > MAX_TEXT_ANSWER:
            raise ValueError(f"«{self.text}»: la respuesta supera los {MAX_TEXT_ANSWER} caracteres")
        return text or None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "text": self.text, "required": self.required,
                "options": list(self.options), "scale_points": self.scale_points,
                "min_label": self.min_label, "max_label": self.max_label}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Question":
        return cls(id=data["id"], kind=data["kind"], text=data["text"], required=bool(data.get("required")),
                   options=tuple(data.get("options") or ()), scale_points=data.get("scale_points"),
                   min_label=data.get("min_label"), max_label=data.get("max_label"))


@dataclass(frozen=True, slots=True)
class Questionnaire:
    """Una versión de un cuestionario; las de un mismo cuestionario comparten
    family_id y la vigente es la que no tiene superseded_at. Una versión usada
    en una sesión no se edita: se crea la siguiente.

    shared_with_group: el docente lo ofrece como plantilla a su grupo.
    """

    id: str
    family_id: str
    version: int
    owner_user_id: str
    title: str
    instructions: str
    created_at: datetime
    questions: tuple[Question, ...] = field(default_factory=tuple)
    shared_with_group: bool = False
    copied_from_id: str | None = None
    superseded_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("id", "family_id", "owner_user_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
        object.__setattr__(self, "title", _text(self.title, "El título", 120))
        object.__setattr__(self, "instructions", _text(self.instructions, "Las indicaciones", 2000, required=False))
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version debe ser un entero positivo")
        questions = tuple(self.questions)
        if not 1 <= len(questions) <= MAX_QUESTIONS:
            raise ValueError(f"Un cuestionario tiene entre 1 y {MAX_QUESTIONS} preguntas")
        if len({item.id for item in questions}) != len(questions):
            raise ValueError("Cada pregunta tiene un identificador propio")
        object.__setattr__(self, "questions", questions)
        for name in ("created_at", "superseded_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")

    @property
    def current(self) -> bool:
        return self.superseded_at is None

    def normalize_answers(self, answers: dict[str, Any]) -> dict[str, Any]:
        """Valida las respuestas y exige las obligatorias. No calcula nada."""
        if not isinstance(answers, dict):
            raise ValueError("Las respuestas no tienen el formato esperado")
        known = {item.id for item in self.questions}
        unknown = set(answers) - known
        if unknown:
            raise ValueError("Hay respuestas a preguntas que no son de este cuestionario")
        result: dict[str, Any] = {}
        missing = []
        for question in self.questions:
            value = question.normalize(answers.get(question.id))
            if value is None:
                if question.required:
                    missing.append(question.text)
                continue
            result[question.id] = value
        if missing:
            raise ValueError("Faltan preguntas obligatorias: " + "; ".join(f"«{text}»" for text in missing))
        return result


@dataclass(frozen=True, slots=True)
class QuestionnaireResponse:
    """Respuestas de una sesión a una versión exacta de un cuestionario.

    answers está en claro solo en memoria; la persistencia lo cifra.
    """

    id: str
    session_id: str
    questionnaire_id: str
    moment: ResponseMoment | str
    answers: dict[str, Any]
    entry_mode: EntryMode | str
    recorded_by_user_id: str
    submitted_at: datetime
    participant_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "moment", ResponseMoment(self.moment))
        object.__setattr__(self, "entry_mode", EntryMode(self.entry_mode))
        if self.submitted_at.tzinfo is None or self.submitted_at.utcoffset() is None:
            raise ValueError("submitted_at debe incluir zona horaria")
