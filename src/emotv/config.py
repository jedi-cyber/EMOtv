# src/emotv/config.py
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# --- Rutas del Proyecto ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")
MODELS_DIR = BASE_DIR / "models"
WEIGHTS_DIR = MODELS_DIR / "weights"
YUNET_PATH = WEIGHTS_DIR / "yunet" / "face_detection_yunet_2026may.onnx"

# --- Configuración de Base de Datos ---
# Se conserva como opcional hasta que se construya el adaptador PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or None
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip() or None
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
N8N_PRODUCTION_WEBHOOK_URL = "https://emotv.app.n8n.cloud/webhook/emi-chat"
CHAT_PROVIDERS = ("sim", "n8n")
DEFAULT_CHAT_RISK_MESSAGE = (
    "Emi no puede ayudarte con este tema. Te pedimos que hables ahora con una "
    "persona de confianza o con un profesional de la salud. Si estás en peligro "
    "o se trata de una emergencia, comunícate de inmediato con los servicios de "
    "emergencia de tu localidad."
)


def get_consent_mode(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    environment = source.get("ENVIRONMENT", "development").strip().lower()
    mode = source.get("CONSENT_MODE", "production" if environment == "production" else "demo").strip().lower()
    if mode not in {"development", "demo", "production"}:
        raise ValueError("CONSENT_MODE debe ser development, demo o production")
    if environment == "production" and mode != "production":
        raise ValueError("Producción no permite desactivar el consentimiento")
    return mode


@dataclass(frozen=True)
class LoginLimits:
    """Límites de intentos fallidos de inicio de sesión."""

    max_failures_per_account: int = 5
    max_failures_per_ip: int = 20
    window_minutes: int = 15


@dataclass(frozen=True)
class ChatSettings:
    """Emi: proveedor del workflow (Sim o n8n), historial, retención, límites de uso y filtro."""

    # sim: workflow desplegado en sim.ai (vigente). n8n: webhook anterior, opcional.
    provider: str = "sim"
    sim_workflow_url: str = ""
    # Obligatoria con Sim: sin ella el chat responde 503. Nunca se escribe en logs.
    sim_api_key: str = field(default="", repr=False)
    webhook_url: str = N8N_PRODUCTION_WEBHOOK_URL
    # Obligatoria con n8n: sin ella el chat responde 503. Nunca se escribe en logs.
    webhook_key: str = field(default="", repr=False)
    # Cada petición incluye dos llamadas a modelos (clasificación y respuesta).
    timeout_seconds: float = 30.0
    history_messages: int = 10
    retention_days: int = 90
    window_messages: int = 20
    window_minutes: int = 10
    daily_messages: int = 200
    max_question_chars: int = 1000
    risk_message: str = DEFAULT_CHAT_RISK_MESSAGE


def get_chat_settings(environ: Mapping[str, str] | None = None) -> ChatSettings:
    source = os.environ if environ is None else environ
    defaults = ChatSettings()

    def number(name: str, default: float, cast=int, minimum: float = 1):
        raw = source.get(name, "").strip()
        try:
            value = cast(raw) if raw else default
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número") from error
        if value < minimum:
            raise ValueError(f"{name} debe ser al menos {minimum:g}")
        return value

    provider = source.get("CHAT_PROVIDER", "").strip().lower() or defaults.provider
    if provider not in CHAT_PROVIDERS:
        raise ValueError("CHAT_PROVIDER debe ser sim o n8n")
    # N8N_TIMEOUT_SECONDS se acepta como nombre anterior de CHAT_TIMEOUT_SECONDS.
    timeout_name = "CHAT_TIMEOUT_SECONDS" if source.get("CHAT_TIMEOUT_SECONDS", "").strip() else "N8N_TIMEOUT_SECONDS"
    return ChatSettings(
        provider=provider,
        sim_workflow_url=source.get("SIM_WORKFLOW_URL", "").strip(),
        sim_api_key=source.get("SIM_API_KEY", "").strip(),
        webhook_url=source.get("N8N_WEBHOOK_URL", "").strip() or defaults.webhook_url,
        webhook_key=source.get("N8N_WEBHOOK_KEY", "").strip(),
        timeout_seconds=number(timeout_name, defaults.timeout_seconds, float, 1),
        history_messages=number("CHAT_HISTORY_MESSAGES", defaults.history_messages, int, 0),
        retention_days=number("CHAT_RETENTION_DAYS", defaults.retention_days),
        window_messages=number("CHAT_LIMIT_WINDOW_MESSAGES", defaults.window_messages),
        window_minutes=number("CHAT_LIMIT_WINDOW_MINUTES", defaults.window_minutes),
        daily_messages=number("CHAT_LIMIT_DAILY_MESSAGES", defaults.daily_messages),
        max_question_chars=number("CHAT_MAX_QUESTION_CHARS", defaults.max_question_chars),
        risk_message=source.get("CHAT_RISK_MESSAGE", "").strip() or defaults.risk_message,
    )


@dataclass(frozen=True)
class LiveExpressionSettings:
    """Condiciones para registrar la expresión elegida en el análisis en vivo."""

    stable_seconds: float = 1.0
    min_confidence: float = 0.5
    # Calibración neutral opcional: aumento mínimo (en proporción, 0.10 = 10
    # puntos) que debe superar una clase respecto a la base para sugerirse.
    calibration_min_increase: float = 0.10
    calibration_seconds: float = 3.0


def get_live_expression_settings(environ: Mapping[str, str] | None = None) -> LiveExpressionSettings:
    source = os.environ if environ is None else environ
    defaults = LiveExpressionSettings()
    values = []
    for name, default, maximum in (("LIVE_STABLE_SECONDS", defaults.stable_seconds, 30.0),
                                   ("LIVE_MIN_CONFIDENCE", defaults.min_confidence, 1.0),
                                   ("LIVE_CALIBRATION_MIN_INCREASE", defaults.calibration_min_increase, 1.0)):
        raw = source.get(name, "").strip()
        try:
            value = float(raw) if raw else default
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número") from error
        if not 0.0 <= value <= maximum:
            raise ValueError(f"{name} debe estar entre 0 y {maximum:g}")
        values.append(value)
    return LiveExpressionSettings(*values)


@dataclass(frozen=True)
class PracticeSettings:
    """Paso de práctica de expresiones (docs/expression-practice.md).

    El nivel es un promedio móvil exponencial de la expresión pedida, con
    constante de tiempo smoothing_seconds. Se considera alcanzado al llegar a
    threshold y deja de estarlo bajo release_threshold (histéresis). Al
    lograrlo, la persona ve el logro success_pause_seconds antes de avanzar.
    """

    threshold: float = 0.6
    release_threshold: float = 0.55
    smoothing_seconds: float = 0.8
    success_pause_seconds: float = 2.0


def get_practice_settings(environ: Mapping[str, str] | None = None) -> PracticeSettings:
    source = os.environ if environ is None else environ
    defaults = PracticeSettings()
    values = []
    for name, default, minimum, maximum in (
        ("PRACTICE_THRESHOLD", defaults.threshold, 0.05, 1.0),
        ("PRACTICE_RELEASE_THRESHOLD", defaults.release_threshold, 0.0, 1.0),
        ("PRACTICE_SMOOTHING_SECONDS", defaults.smoothing_seconds, 0.0, 10.0),
        ("PRACTICE_SUCCESS_PAUSE_SECONDS", defaults.success_pause_seconds, 0.0, 10.0),
    ):
        raw = source.get(name, "").strip()
        try:
            value = float(raw) if raw else default
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número") from error
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} debe estar entre {minimum:g} y {maximum:g}")
        values.append(value)
    settings = PracticeSettings(*values)
    if settings.release_threshold >= settings.threshold:
        raise ValueError("PRACTICE_RELEASE_THRESHOLD debe ser menor que PRACTICE_THRESHOLD")
    return settings


def _default_concurrent_analyses() -> int:
    # Núcleos disponibles para este proceso menos uno (para la API, la base y
    # el servidor web), con mínimo 1. En Docker conviene fijarlo: os.cpu_count
    # ve los núcleos del equipo, no el límite "cpus" del contenedor.
    try:
        cores = len(os.sched_getaffinity(0))
    except AttributeError:
        cores = os.cpu_count() or 1
    return max(1, cores - 1)


@dataclass(frozen=True)
class ServerLoadSettings:
    """Protección del servidor frente a la carga de la lectura en vivo."""

    max_concurrent_analyses: int = field(default_factory=_default_concurrent_analyses)
    max_active_sessions: int = 4
    # Tiempo que una sesión espera un cupo antes de recibir "servidor ocupado".
    busy_wait_seconds: float = 5.0
    # Sin cuadros durante este tiempo (cuando se esperan), el servidor cierra la sesión.
    idle_timeout_seconds: float = 60.0
    # Hilos de onnxruntime por sesión (intra_op), para que las sesiones no compitan.
    onnx_threads_per_session: int = 1


def get_server_load_settings(environ: Mapping[str, str] | None = None) -> ServerLoadSettings:
    source = os.environ if environ is None else environ
    defaults = ServerLoadSettings()
    values: dict[str, float | int] = {}
    for field_name, name, kind, minimum, maximum in (
        ("max_concurrent_analyses", "MAX_CONCURRENT_ANALYSES", int, 1, 256),
        ("max_active_sessions", "MAX_ACTIVE_SESSIONS", int, 1, 1024),
        ("busy_wait_seconds", "ANALYSIS_BUSY_WAIT_SECONDS", float, 0, 60),
        ("idle_timeout_seconds", "LIVE_IDLE_TIMEOUT_SECONDS", float, 5, 3600),
        ("onnx_threads_per_session", "ONNX_THREADS_PER_SESSION", int, 1, 64),
    ):
        raw = source.get(name, "").strip()
        try:
            value = kind(raw) if raw else getattr(defaults, field_name)
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número {'entero' if kind is int else ''}".strip()) from error
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} debe estar entre {minimum:g} y {maximum:g}")
        values[field_name] = value
    return ServerLoadSettings(**values)


@dataclass(frozen=True)
class PrivacySettings:
    """Cuentas de administración y retención de datos."""

    # Cuentas de administrador activas a la vez (por defecto, una persona).
    max_admin_accounts: int = 1
    # Meses que se conserva la auditoría de accesos.
    audit_retention_months: int = 24
    # Meses que se conserva cada sesión con todos sus registros.
    session_retention_months: int = 12


def get_privacy_settings(environ: Mapping[str, str] | None = None) -> PrivacySettings:
    source = os.environ if environ is None else environ
    defaults = PrivacySettings()
    values: dict[str, int] = {}
    for field_name, name, minimum, maximum in (
        ("max_admin_accounts", "MAX_ADMIN_ACCOUNTS", 1, 10),
        ("audit_retention_months", "AUDIT_RETENTION_MONTHS", 1, 120),
        ("session_retention_months", "SESSION_RETENTION_MONTHS", 1, 120),
    ):
        raw = source.get(name, "").strip()
        try:
            value = int(raw) if raw else getattr(defaults, field_name)
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número entero") from error
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} debe estar entre {minimum} y {maximum}")
        values[field_name] = value
    return PrivacySettings(**values)


@dataclass(frozen=True)
class UserImageSettings:
    """Imágenes propias de los usuarios: detección de personas y revisión."""

    # Con esta confianza o más (rostro o cuerpo) la imagen se rechaza y no se guarda.
    person_reject_confidence: float = 0.8
    # Desde esta confianza, se acepta marcada «Revisar: posible persona».
    person_review_confidence: float = 0.4
    # Imágenes propias (pendientes y aprobadas) que puede tener cada usuario.
    upload_limit_per_user: int = 60
    # Días que una imagen espera la revisión del docente antes de eliminarse.
    review_days: int = 30
    # Días antes del vencimiento en que se avisa al usuario.
    expiry_notice_days: int = 7


def get_user_image_settings(environ: Mapping[str, str] | None = None) -> UserImageSettings:
    source = os.environ if environ is None else environ
    defaults = UserImageSettings()
    values: dict[str, float | int] = {}
    for field_name, name, kind, minimum, maximum in (
        ("person_reject_confidence", "IMAGE_PERSON_REJECT_CONFIDENCE", float, 0.05, 1.0),
        ("person_review_confidence", "IMAGE_PERSON_REVIEW_CONFIDENCE", float, 0.05, 1.0),
        ("upload_limit_per_user", "IMAGE_UPLOAD_LIMIT_PER_USER", int, 1, 1000),
        ("review_days", "IMAGE_REVIEW_DAYS", int, 2, 365),
    ):
        raw = source.get(name, "").strip()
        try:
            value = kind(raw) if raw else getattr(defaults, field_name)
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número") from error
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} debe estar entre {minimum} y {maximum}")
        values[field_name] = value
    if values["person_review_confidence"] > values["person_reject_confidence"]:
        raise ValueError("IMAGE_PERSON_REVIEW_CONFIDENCE no puede ser mayor que IMAGE_PERSON_REJECT_CONFIDENCE")
    values["expiry_notice_days"] = min(defaults.expiry_notice_days, int(values["review_days"]) - 1)
    return UserImageSettings(**values)


def get_sensitive_data_keys(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Claves Fernet de SENSITIVE_DATA_KEY, separadas por comas.

    La primera cifra; todas descifran (rotación). Vacía: sin cifrado disponible
    y las sesiones con protocolo no se activan. Nunca se escribe en logs.
    """

    source = os.environ if environ is None else environ
    return tuple(key.strip() for key in source.get("SENSITIVE_DATA_KEY", "").split(",") if key.strip())


def get_login_limits(environ: Mapping[str, str] | None = None) -> LoginLimits:
    source = os.environ if environ is None else environ
    defaults = LoginLimits()
    values = []
    for name, default in (("LOGIN_MAX_FAILURES_PER_ACCOUNT", defaults.max_failures_per_account),
                          ("LOGIN_MAX_FAILURES_PER_IP", defaults.max_failures_per_ip),
                          ("LOGIN_ATTEMPT_WINDOW_MINUTES", defaults.window_minutes)):
        raw = source.get(name, "").strip()
        try:
            value = int(raw) if raw else default
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número entero") from error
        if value < 1:
            raise ValueError(f"{name} debe ser mayor que cero")
        values.append(value)
    return LoginLimits(*values)


def get_mobile_min_app_version(environ: Mapping[str, str] | None = None) -> str:
    """Versión mínima del aplicativo Android aceptada (MOBILE_MIN_APP_VERSION, x.y.z)."""

    source = os.environ if environ is None else environ
    value = source.get("MOBILE_MIN_APP_VERSION", "").strip() or "1.0.0"
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("MOBILE_MIN_APP_VERSION debe tener la forma x.y.z")
    return value


def get_test_data_retention_days(environ: Mapping[str, str] | None = None) -> int:
    """Días que se conservan las cuentas de voluntarios (PRUEBA-NN).

    El consentimiento en papel promete eliminarlas como máximo a los 30 días,
    así que no se acepta un plazo mayor.
    """

    source = os.environ if environ is None else environ
    raw = source.get("TEST_DATA_RETENTION_DAYS", "").strip()
    try:
        days = int(raw) if raw else 30
    except ValueError as error:
        raise ValueError("TEST_DATA_RETENTION_DAYS debe ser un número entero") from error
    if not 1 <= days <= 30:
        raise ValueError("TEST_DATA_RETENTION_DAYS debe estar entre 1 y 30 (plazo del consentimiento)")
    return days


def get_database_url(environ: Mapping[str, str] | None = None) -> str:
    """Obtiene DATABASE_URL y falla de forma explícita si no está configurada."""

    source = os.environ if environ is None else environ
    database_url = source.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL no está configurada. Define la variable de entorno "
            "o crea un archivo .env local a partir de .env.example."
        )
    return database_url


def get_jwt_secret_key(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    secret = source.get("JWT_SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY debe tener al menos 32 caracteres")
    return secret

# --- Configuración de Cámara ---
CAMERA_INDEX = 0
TARGET_WIDTH = 640
TARGET_HEIGHT = 480
TARGET_FPS = 15  # Objetivo de la demo
MAX_VIDEO_FPS = 60  # Límite superior para captura y streaming web

# --- Configuración de Detección Facial (YuNet) ---
YUNET_CONFIDENCE_THRESHOLD = 0.6
YUNET_NMS_THRESHOLD = 0.3

# --- Estrategia de Optimización (Frame Skipping) ---
# Procesar 1 de cada N frames. Con 2, procesamos a 7.5 FPS reales de IA (suficiente)
# si la cámara da 15 FPS. Si da 30 FPS, pon 2 para bajar a 15.
FRAME_SKIP_INTERVAL = 2  # Procesar 1 frame y saltar 1

# --- Backend de OpenCV ---
FORCE_CPU_BACKEND = True  # Evita que intente usar GPU fallando en la PC vieja

# --- Configuración de Recorte y Preprocesamiento Facial ---
FACE_PADDING_RATIO = 0.2  # 20% de padding alrededor del rostro (para contexto)
FACE_TARGET_SIZE = (64, 64)  # Tamaño estándar para modelos de emociones (FER2013)
PREPROCESS_GRAYSCALE = True  # Los modelos de emociones suelen usar escala de grises
PREPROCESS_NORMALIZE = False  # Normalizar píxeles a [0, 1]

# --- Configuración de Modelo de Emociones ---
EMOTION_MODEL_PATH = WEIGHTS_DIR / "emotion" / "emotion-ferplus-8.onnx"
# HSEmotion enet_b0_8_best_afew (EmotiEffLib, commit af83348); ver
# docs/emotion-model-candidates.md.
HSEMOTION_MODEL_PATH = WEIGHTS_DIR / "emotion" / "enet_b0_8_best_afew.onnx"
HSEMOTION_MODEL_URL = (
    "https://github.com/sb-ai-lab/EmotiEffLib/raw/af833487321c3efdcb1768a91a6c656a1986fdf6/"
    "models/affectnet_emotions/onnx/enet_b0_8_best_afew.onnx"
)
HARDLYHUMANS_MODEL_DIR = WEIGHTS_DIR / "hardlyhumans_vit"

# --- Configuracion de Estimacion de Pose ---
POSE_MODEL_PATH = WEIGHTS_DIR / "pose" / "pose_landmarker_lite.task"
POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
POSE_MIN_DETECTION_CONFIDENCE = 0.5
POSE_MIN_PRESENCE_CONFIDENCE = 0.5
POSE_MIN_TRACKING_CONFIDENCE = 0.5
POSE_MIN_LANDMARK_VISIBILITY = 0.5
# Debe superar ARMS_OPEN_WRIST_HEIGHT_TOLERANCE: con 0.02, unos brazos casi
# horizontales contaban a la vez como arms_up y arms_open.
ARMS_UP_WRIST_MARGIN = 0.10
ARMS_UP_ELBOW_TOLERANCE_DEGREES = 25.0
ARMS_OPEN_WRIST_HEIGHT_TOLERANCE = 0.08
ARMS_OPEN_LATERAL_MARGIN = 0.08
ARMS_OPEN_ELBOW_TOLERANCE_DEGREES = 25.0
HANDS_ON_HIPS_DISTANCE_TOLERANCE = 0.12
HANDS_ON_HIPS_MIN_ELBOW_ANGLE = 35.0
HANDS_ON_HIPS_MAX_ELBOW_ANGLE = 135.0
HANDS_ON_HIPS_ELBOW_OUTWARD_MARGIN = 0.03
ARMS_FORWARD_MIN_WRIST_DEPTH = 0.12
ARMS_FORWARD_MIN_ELBOW_DEPTH = 0.04
ARMS_FORWARD_MIN_WRIST_ELBOW_DEPTH = 0.03
ARMS_FORWARD_WRIST_HEIGHT_TOLERANCE = 0.16
ARMS_FORWARD_WRIST_LATERAL_TOLERANCE = 0.25
ARMS_FORWARD_ELBOW_TOLERANCE_DEGREES = 35.0
SQUAT_MIN_KNEE_ANGLE = 65.0
SQUAT_MAX_KNEE_ANGLE = 155.0
SQUAT_MIN_SHOULDER_HIP_GAP = 0.08
SQUAT_MIN_HIP_KNEE_GAP = 0.03
SQUAT_MIN_KNEE_ANKLE_GAP = 0.03
ARMS_UP_HOLD_SECONDS = 5.0
# Hueco máximo sin landmarks utilizables (parpadeo de la detección) que no
# reinicia el tiempo de un paso. Durante el hueco el tiempo no avanza.
POSE_DROPOUT_TOLERANCE_SECONDS = 0.75
EMOTION_INPUT_SIZE = (64, 64)  # Tamaño esperado por el modelo
EMOTION_STABILIZER_WINDOW_SIZE = 7
EMOTION_STABILIZER_MIN_SAMPLES = 5
EMOTION_STABILIZER_MIN_CONFIDENCE = 0.5
EMOTION_STABILIZER_MIN_AGREEMENT = 0.6
EMOTIONAL_ACTIVITY_INSTRUCTION_SECONDS = 3.0
