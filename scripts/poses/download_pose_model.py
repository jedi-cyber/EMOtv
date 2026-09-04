from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path


# Permite ejecutar este archivo directamente antes de instalar EMOtv.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from emotv.config import POSE_MODEL_PATH, POSE_MODEL_URL


def download_pose_model(*, overwrite: bool = False) -> Path:
    """Descarga de forma segura el modelo oficial Pose Landmarker Lite."""

    if POSE_MODEL_PATH.is_file() and not overwrite:
        print(f"El modelo ya existe: {POSE_MODEL_PATH}")
        return POSE_MODEL_PATH

    POSE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = POSE_MODEL_PATH.with_suffix(".task.download")

    print(f"Descargando modelo desde: {POSE_MODEL_URL}")
    print(f"Destino: {POSE_MODEL_PATH}")

    try:
        urllib.request.urlretrieve(POSE_MODEL_URL, temporary_path)
        if temporary_path.stat().st_size == 0:
            raise RuntimeError("El archivo descargado esta vacio")
        temporary_path.replace(POSE_MODEL_PATH)
    except (OSError, RuntimeError, urllib.error.URLError):
        temporary_path.unlink(missing_ok=True)
        raise

    size_mb = POSE_MODEL_PATH.stat().st_size / (1024 * 1024)
    print(f"Modelo descargado correctamente ({size_mb:.1f} MB).")
    return POSE_MODEL_PATH


if __name__ == "__main__":
    download_pose_model()
