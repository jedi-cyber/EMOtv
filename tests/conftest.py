"""Configuración común: las pruebas con modelos reales se saltan sin pesos."""
from __future__ import annotations

import pytest

from emotv.config import EMOTION_MODEL_PATH, POSE_MODEL_PATH, YUNET_PATH

MODEL_WEIGHTS = {
    "YuNet": YUNET_PATH,
    "FER+": EMOTION_MODEL_PATH,
    "MediaPipe Pose": POSE_MODEL_PATH,
}


def missing_weights() -> list[str]:
    return [name for name, path in MODEL_WEIGHTS.items() if not path.is_file()]


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("requires_weights") is None:
        return
    missing = missing_weights()
    if missing:
        pytest.skip(
            f"Faltan pesos de modelos ({', '.join(missing)}); "
            "ejecuta 'python scripts/download_models.py' para correr esta prueba"
        )
