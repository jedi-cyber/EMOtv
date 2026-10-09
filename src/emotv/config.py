# src/emotv/config.py
import os
from collections.abc import Mapping
from dataclasses import dataclass
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
FLOWISE_API_URL = os.getenv("FLOWISE_API_URL", "").strip() or None
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "").strip() or None
FLOWISE_TIMEOUT_SECONDS = float(os.getenv("FLOWISE_TIMEOUT_SECONDS", "20"))


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
class LiveExpressionSettings:
    """Condiciones para registrar la expresión elegida en el análisis en vivo."""

    stable_seconds: float = 1.0
    min_confidence: float = 0.5


def get_live_expression_settings(environ: Mapping[str, str] | None = None) -> LiveExpressionSettings:
    source = os.environ if environ is None else environ
    defaults = LiveExpressionSettings()
    values = []
    for name, default, maximum in (("LIVE_STABLE_SECONDS", defaults.stable_seconds, 30.0),
                                   ("LIVE_MIN_CONFIDENCE", defaults.min_confidence, 1.0)):
        raw = source.get(name, "").strip()
        try:
            value = float(raw) if raw else default
        except ValueError as error:
            raise ValueError(f"{name} debe ser un número") from error
        if not 0.0 <= value <= maximum:
            raise ValueError(f"{name} debe estar entre 0 y {maximum:g}")
        values.append(value)
    return LiveExpressionSettings(*values)


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
ARMS_UP_WRIST_MARGIN = 0.02
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
EMOTION_INPUT_SIZE = (64, 64)  # Tamaño esperado por el modelo
EMOTION_STABILIZER_WINDOW_SIZE = 7
EMOTION_STABILIZER_MIN_SAMPLES = 5
EMOTION_STABILIZER_MIN_CONFIDENCE = 0.5
EMOTION_STABILIZER_MIN_AGREEMENT = 0.6
EMOTIONAL_ACTIVITY_INSTRUCTION_SECONDS = 3.0
