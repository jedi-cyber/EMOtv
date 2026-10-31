"""Sesión que ejecuta un protocolo: cuestionario previo, calibración, estímulos y
cuestionario posterior. En el aplicativo móvil, una sesión sin protocolo usa la
fase live: calibración y registro periódico de la expresión, sin estímulos.

La estación de un examen simulado espera el consentimiento (waiting), se
calibra, espera el inicio (ready) y registra una fila cada medio segundo
(exam) hasta que el docente termina el examen.

La autorización se confirma una sola vez, al iniciar la sesión.

Las capturas guardan solo la expresión estimada por el modelo local, su
distribución y un indicador de calidad: nunca la imagen ni datos de identidad.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from emotv.domain.protocol import PRACTICE_TARGETS

# Aviso fijo en cada pantalla y cada reporte con imágenes abstractas.
ABSTRACT_NOTICE = "Registro descriptivo. Una sesión breve no permite sacar conclusiones a partir de una imagen."

QUALITY_RETRY_SECONDS = 3.0        # reintento antes de guardar una captura marcada
ABSTRACT_CAPTURE_INTERVAL = 3.0    # una imagen abstracta se captura varias veces
MAX_NOTE_LENGTH = 300
EXAM_CAPTURE_INTERVAL = 0.5        # una fila cada medio segundo durante el examen
EXAM_GAP_SECONDS = 1.5             # sin cuadros tras este margen, la fila se guarda marcada

# Lo que lee la persona en un ejercicio de práctica: corto y sin valorar.
PRACTICE_INSTRUCTIONS = {
    "happiness": "Muestra alegría",
    "surprise": "Muestra sorpresa",
    "sadness": "Muestra tristeza",
    "anger": "Muestra enojo",
    "fear": "Muestra miedo",
    "disgust": "Muestra asco",
    "neutral": "Deja la cara tranquila",
    "contempt": "Muestra desprecio",
}
PRACTICE_ACHIEVED_MESSAGE = "¡Lo lograste!"
# Aviso fijo junto a todo resultado de práctica.
PRACTICE_NOTICE = ("Los modelos de expresión se entrenaron principalmente con rostros de adultos y su "
                   "precisión con niños no está validada. El resultado describe el ejercicio, no el "
                   "estado emocional de la persona.")

# Debriefing: lo que ve la persona al terminar el examen. Describe qué se
# registró, sin valorar ni diagnosticar.
EXAM_DEBRIEFING = (
    "Gracias por participar. Durante el examen, EMOtv estimó cada medio segundo la expresión facial "
    "que mostraba tu rostro, por ejemplo neutral, sorpresa o alegría. No se guardó ninguna imagen tuya: "
    "cada cuadro de la cámara se analizó en memoria y se descartó. Solo quedó un registro con el código "
    "de tu sesión, la expresión estimada, su confianza y el segundo del examen. Es un registro descriptivo "
    "de expresiones faciales: no indica lo que sentiste ni es un diagnóstico. Si tienes preguntas, "
    "consulta a tu docente."
)


class GuidedPhase(str, Enum):
    PRE_QUESTIONNAIRE = "pre_questionnaire"
    BEFORE_ANALYZER = "before_analyzer"   # imágenes abstractas antes del analizador, sin capturas
    CALIBRATION = "calibration"
    STIMULI = "stimuli"
    POST_QUESTIONNAIRE = "post_questionnaire"
    LIVE = "live"                         # sin protocolo (móvil): registro periódico hasta terminar
    WAITING = "waiting"                   # estación de examen sin consentimiento: no se analiza nada
    READY = "ready"                       # estación calibrada: espera que el docente inicie
    EXAM = "exam"                         # examen en curso: una fila cada medio segundo
    FINISHED = "finished"
    STOPPED = "stopped"


TERMINAL_PHASES = frozenset({GuidedPhase.FINISHED, GuidedPhase.STOPPED})
EXAM_STATION_PHASES = frozenset({GuidedPhase.WAITING, GuidedPhase.READY, GuidedPhase.EXAM})


class StopReason(str, Enum):
    PARTICIPANT = "participant"   # la persona analizada pidió parar
    GUARDIAN = "guardian"         # el padre, la madre o el tutor pidió parar
    CONDUCTOR = "conductor"       # quien conduce la sesión la terminó


class MarkerKind(str, Enum):
    DISTRACTED = "distracted"     # se distrajo
    LAUGHED = "laughed"           # se rió
    ASKED_TO_STOP = "asked_to_stop"  # pidió parar
    CRIED = "cried"               # lloró
    NOTE = "note"                 # nota libre breve (cifrada)


class QualityIssue(str, Enum):
    NO_FRAME = "no_frame"         # no llegó ningún cuadro de la cámara
    NO_FACE = "no_face"
    OFF_CENTER = "off_center"
    TOO_SMALL = "too_small"
    TOO_DARK = "too_dark"
    TOO_BRIGHT = "too_bright"
    TILTED = "tilted"


class PracticeOutcome(str, Enum):
    ACHIEVED = "achieved"         # sostuvo la expresión pedida el tiempo indicado
    TIMED_OUT = "timed_out"       # venció el tiempo máximo sin lograrla
    SKIPPED = "skipped"           # quien conduce saltó el ejercicio
    STOPPED = "stopped"           # la sesión se detuvo durante el ejercicio


class CaptureQuality(str, Enum):
    GOOD = "good"
    FLAGGED = "flagged"           # se guardó con un problema de calidad


@dataclass(frozen=True, slots=True)
class GuidedRun:
    """Estado de una sesión guiada, compartido por la vista de quien conduce y
    la pantalla de la persona. view_token_hash es el SHA-256 del enlace de esa
    pantalla; el enlace en claro solo se entrega al crearlo."""

    session_id: str
    owner_user_id: str
    created_at: datetime
    phase: GuidedPhase | str = GuidedPhase.CALIBRATION
    confirmed_at: datetime | None = None
    step_index: int = 0
    step_started_at: datetime | None = None
    next_capture_due: float | None = None
    steps_log: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    calibrated_at: datetime | None = None
    view_token_hash: str | None = None
    ended_at: datetime | None = None
    stop_reason: StopReason | str | None = None
    # En los ejercicios de práctica, la persona ve la señal del nivel; quien
    # conduce puede apagarla para toda la sesión.
    practice_feedback: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "phase", GuidedPhase(self.phase))
        if self.stop_reason is not None:
            object.__setattr__(self, "stop_reason", StopReason(self.stop_reason))
        if (self.phase is GuidedPhase.STOPPED) != (self.stop_reason is not None):
            raise ValueError("Una sesión detenida registra quién pidió parar")
        object.__setattr__(self, "steps_log", tuple(self.steps_log))

    @property
    def active(self) -> bool:
        return self.phase not in TERMINAL_PHASES


@dataclass(frozen=True, slots=True)
class FrameAssessment:
    """Resultado de analizar un cuadro en memoria; la imagen ya se descartó."""

    issues: tuple[QualityIssue, ...]
    emotion: str | None = None
    confidence: float | None = None
    distribution: dict[str, float] | None = None

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True)
class ExpressionCapture:
    """Una captura: sin imagen ni datos de identidad. stimulus_id es nulo en el
    registro sin protocolo (fase live)."""

    id: str
    session_id: str
    captured_at: datetime
    emotion_model_id: str
    emotion_model_version: str
    quality: CaptureQuality | str
    quality_issues: tuple[QualityIssue, ...]
    step_index: int
    stimulus_id: str | None
    seconds_since_stimulus: float
    emotion: str | None = None
    confidence: float | None = None
    distribution: dict[str, float] | None = None
    # Clase que más aumentó respecto de la base neutral, si hubo calibración.
    calibrated_emotion: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "quality", CaptureQuality(self.quality))
        object.__setattr__(self, "quality_issues", tuple(QualityIssue(item) for item in self.quality_issues))
        if (self.quality is CaptureQuality.GOOD) == bool(self.quality_issues):
            raise ValueError("Una captura marcada indica su problema de calidad; una buena, ninguno")
        if (self.emotion is None) != (self.confidence is None):
            raise ValueError("La expresión estimada y su confianza se registran juntas")


@dataclass(frozen=True, slots=True)
class SessionMarker:
    """Marcador con hora de quien conduce la sesión; note solo en memoria en claro."""

    id: str
    session_id: str
    kind: MarkerKind | str
    occurred_at: datetime
    recorded_by_user_id: str
    step_index: int | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        kind = MarkerKind(self.kind)
        object.__setattr__(self, "kind", kind)
        note = (self.note or "").strip() or None
        if kind is MarkerKind.NOTE and note is None:
            raise ValueError("Escribe la nota")
        if note is not None and len(note) > MAX_NOTE_LENGTH:
            raise ValueError(f"La nota supera los {MAX_NOTE_LENGTH} caracteres")
        object.__setattr__(self, "note", note)


@dataclass(frozen=True, slots=True)
class VerbalResponse:
    """Lo que la persona dice ver en una imagen abstracta, tal como lo dijo.
    EMOtv no lo interpreta ni lo relaciona con ninguna condición."""

    id: str
    session_id: str
    step_index: int
    stimulus_id: str
    text: str
    recorded_at: datetime
    recorded_by_user_id: str

    def __post_init__(self) -> None:
        text = (self.text or "").strip()
        if not text:
            raise ValueError("Escribe lo que dijo ver")
        if len(text) > MAX_NOTE_LENGTH:
            raise ValueError(f"El texto supera los {MAX_NOTE_LENGTH} caracteres")
        object.__setattr__(self, "text", text)


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} debe incluir zona horaria")


@dataclass(frozen=True, slots=True)
class PracticeResult:
    """Resultado de un ejercicio de práctica: describe qué ocurrió, sin valorar
    a la persona. No guarda imágenes, niveles por cuadro ni la base neutral.

    peak_level es el nivel máximo (0 a 1) que alcanzó la señal.
    relative_to_calibration indica si el nivel se midió respecto de la base
    neutral de la sesión; feedback_visible, si la persona vio la señal durante
    todo el ejercicio. analyzed_frames y flagged_frames cuentan los cuadros con
    rostro y los descartados por calidad."""

    id: str
    session_id: str
    step_index: int
    target_expression: str
    outcome: PracticeOutcome | str
    peak_level: float
    relative_to_calibration: bool
    feedback_visible: bool
    analyzed_frames: int
    flagged_frames: int
    emotion_model_id: str
    emotion_model_version: str
    started_at: datetime
    ended_at: datetime
    seconds_to_achieve: float | None = None

    def __post_init__(self) -> None:
        for name in ("id", "session_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
        outcome = PracticeOutcome(self.outcome)
        object.__setattr__(self, "outcome", outcome)
        if self.target_expression not in PRACTICE_TARGETS:
            raise ValueError("La expresión pedida no es válida")
        for name in ("step_index", "analyzed_frames", "flagged_frames"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} debe ser un entero no negativo")
        if not 0.0 <= self.peak_level <= 1.0:
            raise ValueError("El nivel máximo está entre 0 y 1")
        _aware("started_at", self.started_at)
        _aware("ended_at", self.ended_at)
        if self.ended_at < self.started_at:
            raise ValueError("El ejercicio termina después de empezar")
        if (outcome is PracticeOutcome.ACHIEVED) != (self.seconds_to_achieve is not None):
            raise ValueError("Solo un ejercicio logrado registra los segundos hasta lograrlo")
        if self.seconds_to_achieve is not None and self.seconds_to_achieve < 0:
            raise ValueError("Los segundos hasta lograrlo no son negativos")

    @property
    def achieved(self) -> bool:
        return self.outcome is PracticeOutcome.ACHIEVED
