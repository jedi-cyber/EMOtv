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

from emotv.domain.expression_info import EXPRESSION_KEYS
from emotv.domain.protocol import PRACTICE_TARGETS

# Aviso fijo en cada pantalla y cada reporte con imágenes abstractas.
ABSTRACT_NOTICE = "Registro descriptivo. Una sesión breve no permite sacar conclusiones a partir de una imagen."

QUALITY_RETRY_SECONDS = 3.0        # reintento antes de guardar una captura marcada
ABSTRACT_CAPTURE_INTERVAL = 3.0    # una imagen abstracta se captura varias veces
MAX_NOTE_LENGTH = 300
# Intentos de un reconocimiento o un ejercicio: el primero y hasta dos repeticiones.
MAX_STEP_ATTEMPTS = 3
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
# Imitar un modelo: la ilustración muestra la cara que se pide.
IMITATION_INSTRUCTION = "Haz la misma cara"
PRACTICE_ACHIEVED_MESSAGE = "¡Lo lograste!"
# Aviso fijo junto a todo resultado de práctica.
PRACTICE_NOTICE = ("Los modelos de expresión se entrenaron principalmente con rostros de adultos y su "
                   "precisión con niños no está validada. El resultado describe el ejercicio, no el "
                   "estado emocional de la persona.")

# Reconocimiento: la pregunta, el nombre de cada opción y lo que se lee después
# de responder (o al vencer el tiempo). Solo nombra la emoción de la imagen;
# no dice si la persona acertó ni la valora.
RECOGNITION_QUESTION = "¿Qué emoción es?"
# Con una situación se pregunta por la cara de la imagen, no por lo que alguien
# siente: una situación no tiene una única respuesta emocional.
SITUATION_QUESTION = "¿Qué emoción muestra la cara?"
# Aviso fijo junto a todo resultado de reconocimiento.
RECOGNITION_NOTICE = ("Describe las respuestas de esta práctica. Una sesión breve no permite sacar conclusiones "
                      "sobre cómo reconoce emociones la persona.")
RECOGNITION_NAMES = {
    "happiness": "Alegría",
    "surprise": "Sorpresa",
    "sadness": "Tristeza",
    "anger": "Enojo",
    "fear": "Miedo",
    "disgust": "Asco",
    "neutral": "Cara tranquila",
    "contempt": "Desprecio",
}
RECOGNITION_ANSWERS = {
    "happiness": "Es alegría",
    "surprise": "Es sorpresa",
    "sadness": "Es tristeza",
    "anger": "Es enojo",
    "fear": "Es miedo",
    "disgust": "Es asco",
    "neutral": "Es una cara tranquila",
    "contempt": "Es desprecio",
}
# Lo que se lee al terminar un paso con situación: la expresión de la imagen y
# que otras personas podrían sentir algo distinto.
SITUATION_ANSWERS = {
    "happiness": "La cara de la imagen muestra alegría.",
    "surprise": "La cara de la imagen muestra sorpresa.",
    "sadness": "La cara de la imagen muestra tristeza.",
    "anger": "La cara de la imagen muestra enojo.",
    "fear": "La cara de la imagen muestra miedo.",
    "disgust": "La cara de la imagen muestra asco.",
    "neutral": "La cara de la imagen está tranquila.",
    "contempt": "La cara de la imagen muestra desprecio.",
}
SITUATION_NOTE = "En una situación así, cada persona puede sentir algo distinto."
# Distractoras: las básicas y la cara tranquila. Desprecio solo aparece cuando
# es la respuesta correcta: es poco común y difícil de nombrar para un niño.
RECOGNITION_DISTRACTORS = ("happiness", "sadness", "anger", "fear", "surprise", "disgust", "neutral")
# Paso de dibujo: la persona dibuja en su pantalla y después señala qué emoción
# quiso representar. El dibujo no sale del dispositivo y no se interpreta: solo
# se registra la emoción que señaló y los tiempos.
DRAWING_INSTRUCTION = "Dibuja una cara que muestre una emoción."
DRAWING_QUESTION = "¿Qué emoción quisiste dibujar?"
# Aviso fijo junto a todo resultado de dibujo.
DRAWING_NOTICE = ("Describe la emoción que la persona señaló en cada dibujo. EMOtv no ve ni interpreta los "
                  "dibujos: se quedan en la pantalla de la persona y se borran al terminar el paso.")
DRAWING_OPTIONS = ("happiness", "sadness", "anger", "fear", "surprise", "disgust", "neutral")
# Juego de emparejar: la persona relaciona cada imagen con el nombre de su
# emoción. Sin puntaje: si no la encuentra, se le muestra con su explicación y
# el juego sigue. Solo se guardan contadores (GameResult).
GAME_QUESTION = "¿Qué emoción muestra esta cara?"
GAME_RETRY = "Mira otra vez la cara. Puedes pedir ayuda."
# Si ya pidió ayuda en la ronda, no se le vuelve a ofrecer.
GAME_RETRY_HELPED = "Mira otra vez la cara."
GAME_FOUND = "Lo encontraste: {answer}."
GAME_SHOWN = "{answer}."
# Buscar la misma emoción: la imagen modelo arriba y otras caras para elegir.
SIMILAR_QUESTION = "¿Qué cara muestra la misma emoción que la de arriba?"
SIMILAR_RETRY = "Mira otra vez la cara de arriba. Puedes pedir ayuda."
SIMILAR_RETRY_HELPED = "Mira otra vez la cara de arriba."
SIMILAR_FOUND = "Lo encontraste: las dos caras muestran la misma emoción, {answer}."
SIMILAR_SHOWN = "Esta cara muestra la misma emoción: {answer}."
GAME_FINISHED = "Terminaste el juego."
GAME_TIME_UP = "Terminó el tiempo del juego."
# Tras este número de opciones distintas a la de la imagen, se muestra la respuesta.
GAME_MISSES_BEFORE_ANSWER = 2
GAME_NOTICE = ("Describe lo que ocurrió en el juego. Una sesión breve no permite sacar conclusiones sobre cómo "
               "reconoce emociones la persona.")
# Describe lo que la persona eligió; no se compara con el dibujo.
DRAWING_ANSWERS = {
    "happiness": "Dibujaste alegría.",
    "sadness": "Dibujaste tristeza.",
    "anger": "Dibujaste enojo.",
    "fear": "Dibujaste miedo.",
    "surprise": "Dibujaste sorpresa.",
    "disgust": "Dibujaste asco.",
    "neutral": "Dibujaste una cara tranquila.",
}

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
    READY = "ready"                       # estación calibrada, o sesión sin cámara: espera que se inicie
    EXAM = "exam"                         # examen en curso: una fila cada medio segundo
    FINISHED = "finished"
    STOPPED = "stopped"


TERMINAL_PHASES = frozenset({GuidedPhase.FINISHED, GuidedPhase.STOPPED})

# Vinculación de un dispositivo Android como pantalla de la persona: quien
# conduce pide un código en la web y el aplicativo lo canjea, una sola vez y
# antes de que venza, por el enlace de esa pantalla. Sin 0/O ni 1/I/L.
PAIRING_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
PAIRING_LENGTH = 8
PAIRING_SECONDS = 300
VIEW_DEVICES = ("web", "android")
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


class RecognitionOutcome(str, Enum):
    ANSWERED = "answered"         # se eligió una opción
    TIMED_OUT = "timed_out"       # venció el tiempo sin respuesta
    SKIPPED = "skipped"           # quien conduce saltó el paso
    STOPPED = "stopped"           # la sesión se detuvo durante el paso


class RecognitionAnswerer(str, Enum):
    PARTICIPANT = "participant"   # tocó la opción en su pantalla
    CONDUCTOR = "conductor"       # quien conduce registró lo que señaló o dijo


# Motivos que informa la pantalla de la persona cuando no puede usar la cámara.
CAMERA_PROBLEMS = frozenset({"denied", "busy", "not_found", "insecure", "unknown"})
# Motivo en steps_log de un paso que se saltó porque la sesión siguió sin cámara.
NO_CAMERA_SKIP = "no_camera"


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
    # Quien conduce siguió sin cámara (permiso denegado, sin cámara o falla): desde
    # entonces no se calibra y los pasos que la necesitan se saltan.
    camera_off_at: datetime | None = None
    # Intento del paso en curso: 1 al empezarlo; «Repetir este paso» lo aumenta.
    step_attempt: int = 1
    # Juego de emparejar en curso: ronda, opciones descartadas y contadores. De
    # tamaño fijo; se reinicia con cada paso o intento.
    game_progress: dict[str, Any] | None = None
    # Código pendiente para vincular Android (solo su SHA-256) y cuándo vence.
    pairing_hash: str | None = None
    pairing_expires_at: datetime | None = None
    # Dónde se abre la pantalla de la persona: el enlace web o Android.
    view_device: str = "web"

    def __post_init__(self) -> None:
        object.__setattr__(self, "phase", GuidedPhase(self.phase))
        if self.view_device not in VIEW_DEVICES:
            raise ValueError("La pantalla de la persona es web o Android")
        if (self.pairing_hash is None) != (self.pairing_expires_at is None):
            raise ValueError("Un código de vinculación tiene su vencimiento")
        _check_attempt(self.step_attempt)
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


def _check_attempt(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_STEP_ATTEMPTS:
        raise ValueError(f"El intento está entre 1 y {MAX_STEP_ATTEMPTS}")


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
    # 1 es el primero; las métricas y las estadísticas cuentan solo ese.
    attempt: int = 1

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
        _check_attempt(self.attempt)

    @property
    def achieved(self) -> bool:
        return self.outcome is PracticeOutcome.ACHIEVED


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    """Resultado de un paso de reconocimiento: qué opciones se mostraron, cuál se
    eligió y en cuánto tiempo. Describe la respuesta; no valora a la persona ni
    analiza la cámara."""

    id: str
    session_id: str
    step_index: int
    stimulus_id: str
    target_expression: str
    options: tuple[str, ...]
    outcome: RecognitionOutcome | str
    started_at: datetime
    ended_at: datetime
    chosen_expression: str | None = None
    seconds_to_answer: float | None = None
    answered_by: RecognitionAnswerer | str | None = None
    # 1 es el primero; las métricas y las estadísticas cuentan solo ese.
    attempt: int = 1

    def __post_init__(self) -> None:
        for name in ("id", "session_id", "stimulus_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
        outcome = RecognitionOutcome(self.outcome)
        object.__setattr__(self, "outcome", outcome)
        if isinstance(self.step_index, bool) or not isinstance(self.step_index, int) or self.step_index < 0:
            raise ValueError("step_index debe ser un entero no negativo")
        options = tuple(self.options)
        object.__setattr__(self, "options", options)
        if len(set(options)) != len(options) or any(item not in EXPRESSION_KEYS for item in options):
            raise ValueError("Las opciones son expresiones distintas del catálogo")
        if self.target_expression not in options:
            raise ValueError("La expresión de la imagen está entre las opciones")
        answered = outcome is RecognitionOutcome.ANSWERED
        if answered != (self.chosen_expression is not None) or answered != (self.seconds_to_answer is not None)                 or answered != (self.answered_by is not None):
            raise ValueError("Solo un paso respondido registra la opción, los segundos y quién respondió")
        if self.chosen_expression is not None and self.chosen_expression not in options:
            raise ValueError("La opción elegida está entre las que se mostraron")
        if self.answered_by is not None:
            object.__setattr__(self, "answered_by", RecognitionAnswerer(self.answered_by))
        if self.seconds_to_answer is not None and self.seconds_to_answer < 0:
            raise ValueError("Los segundos hasta responder no son negativos")
        _aware("started_at", self.started_at)
        _aware("ended_at", self.ended_at)
        if self.ended_at < self.started_at:
            raise ValueError("El paso termina después de empezar")
        _check_attempt(self.attempt)

    @property
    def matched(self) -> bool | None:
        """Si la opción elegida es la expresión de la imagen; None sin respuesta."""
        return None if self.chosen_expression is None else self.chosen_expression == self.target_expression


class GameOutcome(str, Enum):
    COMPLETED = "completed"       # se jugaron todas las rondas
    TIMED_OUT = "timed_out"       # venció el tiempo del juego
    SKIPPED = "skipped"           # quien conduce saltó el paso
    STOPPED = "stopped"           # la sesión se detuvo durante el juego


@dataclass(frozen=True, slots=True)
class GameResult:
    """Resultado de un juego de emparejar: solo contadores, uno por paso e
    intento. rounds_done son las rondas terminadas (encontrada o mostrada);
    matched, las que la persona emparejó; first_try, las emparejadas sin elegir
    antes otra opción; help_used, las rondas en que pidió ayuda; by_conductor,
    las respuestas que registró quien conduce. No es un puntaje."""

    id: str
    session_id: str
    step_index: int
    game_type: str
    outcome: GameOutcome | str
    started_at: datetime
    ended_at: datetime
    rounds_total: int
    rounds_done: int = 0
    matched: int = 0
    first_try: int = 0
    help_used: int = 0
    by_conductor: int = 0
    attempt: int = 1

    def __post_init__(self) -> None:
        for name in ("id", "session_id", "game_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
        object.__setattr__(self, "outcome", GameOutcome(self.outcome))
        for name in ("step_index", "rounds_total", "rounds_done", "matched", "first_try", "help_used",
                     "by_conductor"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} debe ser un entero no negativo")
        if not (self.first_try <= self.matched <= self.rounds_done <= self.rounds_total
                and self.help_used <= self.rounds_done + 1 and self.help_used <= self.rounds_total):
            raise ValueError("Los contadores del juego no cuadran")
        if (self.outcome is GameOutcome.COMPLETED) != (self.rounds_done == self.rounds_total):
            raise ValueError("Un juego completo tiene todas sus rondas terminadas")
        _aware("started_at", self.started_at)
        _aware("ended_at", self.ended_at)
        if self.ended_at < self.started_at:
            raise ValueError("El paso termina después de empezar")
        _check_attempt(self.attempt)


@dataclass(frozen=True, slots=True)
class DrawingResult:
    """Resultado de un paso de dibujo: la emoción que la persona señaló y en
    cuánto tiempo. El dibujo nunca llega al servidor; no hay respuesta correcta
    ni se compara la emoción elegida con el dibujo."""

    id: str
    session_id: str
    step_index: int
    outcome: RecognitionOutcome | str
    started_at: datetime
    ended_at: datetime
    chosen_expression: str | None = None
    seconds_to_answer: float | None = None
    answered_by: RecognitionAnswerer | str | None = None
    # 1 es el primero; un paso repetido guarda cada intento.
    attempt: int = 1

    def __post_init__(self) -> None:
        for name in ("id", "session_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} es obligatorio")
        outcome = RecognitionOutcome(self.outcome)
        object.__setattr__(self, "outcome", outcome)
        if isinstance(self.step_index, bool) or not isinstance(self.step_index, int) or self.step_index < 0:
            raise ValueError("step_index debe ser un entero no negativo")
        answered = outcome is RecognitionOutcome.ANSWERED
        if answered != (self.chosen_expression is not None) or answered != (self.seconds_to_answer is not None) \
                or answered != (self.answered_by is not None):
            raise ValueError("Solo un paso respondido registra la emoción, los segundos y quién respondió")
        if self.chosen_expression is not None and self.chosen_expression not in DRAWING_OPTIONS:
            raise ValueError("La emoción elegida está entre las que se muestran")
        if self.answered_by is not None:
            object.__setattr__(self, "answered_by", RecognitionAnswerer(self.answered_by))
        if self.seconds_to_answer is not None and self.seconds_to_answer < 0:
            raise ValueError("Los segundos hasta responder no son negativos")
        _aware("started_at", self.started_at)
        _aware("ended_at", self.ended_at)
        if self.ended_at < self.started_at:
            raise ValueError("El paso termina después de empezar")
        _check_attempt(self.attempt)
