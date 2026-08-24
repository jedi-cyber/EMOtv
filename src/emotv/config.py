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

# --- Configuración de Detección Facial (YuNet) ---
YUNET_CONFIDENCE_THRESHOLD = 0.6
YUNET_NMS_THRESHOLD = 0.3

# --- Estrategia de Optimización (Frame Skipping) ---
# Procesar 1 de cada N frames. Con 2, procesamos a 7.5 FPS reales de IA (suficiente)
# si la cámara da 15 FPS. Si da 30 FPS, pon 2 para bajar a 15.
FRAME_SKIP_INTERVAL = 2  # Procesar 1 frame y saltar 1

# --- Backend de OpenCV ---
FORCE_CPU_BACKEND = True  # Evita que intente usar GPU fallando en la PC vieja