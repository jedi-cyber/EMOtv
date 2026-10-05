from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from emotv.config import EMOTION_MODEL_PATH, YUNET_PATH

if not (YUNET_PATH.is_file() and EMOTION_MODEL_PATH.is_file()):
    pytest.skip("La app carga YuNet y FER+ al importarse; faltan los pesos", allow_module_level=True)

from emotv.interfaces.web import app as app_module  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app_module.app, base_url="http://localhost")


def test_health_ok_when_database_and_weights_available(client, monkeypatch):
    monkeypatch.setattr(app_module, "_database_status", lambda: "ok")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {
        "database": "ok", "face_detector": "ok", "emotion_model": "ok"}}


def test_health_503_without_database(client, monkeypatch):
    monkeypatch.setattr(app_module, "_database_status", lambda: "unavailable")

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unavailable"


def test_health_503_without_weights_and_hides_paths(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "_database_status", lambda: "ok")
    monkeypatch.setattr(app_module, "YUNET_PATH", tmp_path / "missing.onnx")

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["checks"]["face_detector"] == "missing"
    assert str(tmp_path) not in response.text and "onnx" not in response.text
