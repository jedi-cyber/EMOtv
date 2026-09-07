# src/emotv/config.py
from pathlib import Path

# --- Rutas del Proyecto ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
WEIGHTS_DIR = MODELS_DIR / "weights"
YUNET_PATH = WEIGHTS_DIR / "yunet" / "face_detection_yunet_2026may.onnx"

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
ARMS_UP_HOLD_SECONDS = 5.0
EMOTION_INPUT_SIZE = (64, 64)  # Tamaño esperado por el modelo
EMOTION_STABILIZER_WINDOW_SIZE = 7
EMOTION_STABILIZER_MIN_SAMPLES = 5
EMOTION_STABILIZER_MIN_CONFIDENCE = 0.5
EMOTION_STABILIZER_MIN_AGREEMENT = 0.6
EMOTIONAL_ACTIVITY_INSTRUCTION_SECONDS = 3.0
