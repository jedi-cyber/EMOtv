"""Humo con los pesos reales: se salta en máquinas sin modelos descargados."""
from __future__ import annotations

import numpy as np
import pytest

from emotv.infrastructure.vision.face_detection.yunet_face_detector import YuNetFaceDetector
from scripts import download_models


def test_missing_yunet_points_to_download_models(tmp_path):
    with pytest.raises(FileNotFoundError, match="scripts/download_models.py"):
        YuNetFaceDetector(model_path=tmp_path / "face_detection_yunet_2026may.onnx")


@pytest.mark.requires_weights
def test_installed_weights_match_download_models_hashes():
    # Garantiza que YuNet es el archivo 2026may publicado y no otra versión renombrada.
    assert download_models.ensure_weights(check_only=True) == []


@pytest.mark.requires_weights
def test_real_models_load_and_ignore_frame_without_person():
    from emotv.application import PoseService
    from emotv.infrastructure.vision.emotion_classifier.emotion_frame_analyzer import EmotionFrameAnalyzer

    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    pose = PoseService()
    try:
        assert EmotionFrameAnalyzer().analyze(blank) is None
        assert pose.analyze(blank) is None
    finally:
        pose.close()
