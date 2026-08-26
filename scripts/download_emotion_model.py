from pathlib import Path
import urllib.request

# Ruta donde guardaremos el modelo
MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "weights" / "emotion"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# URL del modelo FER+ en ONNX (versión ligera)
# Fuente: https://huggingface.co/onnxmodelzoo/emotion-ferplus-8
URL = "https://huggingface.co/onnxmodelzoo/emotion-ferplus-8/resolve/main/emotion-ferplus-8.onnx"

OUTPUT_PATH = MODEL_DIR / "emotion-ferplus-8.onnx"

print(f"Descargando modelo de emociones desde: {URL}")
print(f"Guardando en: {OUTPUT_PATH}")

try:
    urllib.request.urlretrieve(URL, OUTPUT_PATH)
    print("✅ Descarga completada.")
except Exception as e:
    print(f"❌ Error: {e}")
    print("Puedes descargar manualmente desde: https://huggingface.co/onnxmodelzoo/emotion-ferplus-8")