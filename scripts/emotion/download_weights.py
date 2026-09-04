# scripts/download_weights.py
import urllib.request
from pathlib import Path
import sys

# Añade la ruta raíz al sys.path para poder importar emotv
sys.path.append(str(Path(__file__).resolve().parent.parent))
from emotv.config import YUNET_PATH, WEIGHTS_DIR

def download_model():
    # URL oficial del modelo YuNet de OpenCV (versión 2023 o 2026, usa la que necesites)
    url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    
    # Crea la carpeta si no existe
    YUNET_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Descargando modelo desde {url}...")
    print(f"Guardando en: {YUNET_PATH}")
    
    try:
        urllib.request.urlretrieve(url, str(YUNET_PATH))
        print("¡Descarga completada!")
    except Exception as e:
        print(f"Error al descargar: {e}")
        print("Descárgalo manualmente desde la web de OpenCV.")

if __name__ == "__main__":
    download_model()