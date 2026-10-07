"""/health y / tras retirar la cámara del servidor; la app se importa sin pesos."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from emotv.interfaces.web import app as app_module


@pytest.fixture
def client():
    return TestClient(app_module.app, base_url="http://localhost")


def test_root_returns_simple_status(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"service": "emotv-api", "status": "running"}


@pytest.mark.parametrize("method, path", [
    ("GET", "/video_feed"), ("GET", "/emotion"), ("GET", "/stats"),
    ("GET", "/control?action=start"), ("POST", "/control/start"),
    ("GET", "/web"), ("GET", "/static/js/script.js"),
])
def test_server_camera_routes_no_longer_exist(client, method, path):
    assert client.request(method, path).status_code == 404


def test_server_camera_websocket_no_longer_exists(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/emotions"):
            pass


def test_health_ok_when_database_and_weights_available(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "_database_status", lambda: "ok")
    for name in ("YUNET_PATH", "EMOTION_MODEL_PATH"):
        weights = tmp_path / f"{name}.onnx"
        weights.write_bytes(b"x")
        monkeypatch.setattr(app_module, name, weights)

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
