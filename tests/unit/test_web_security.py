from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from emotv.interfaces.web.security import WebSecuritySettings, configure_web_security, load_web_settings


def security_app():
    app = FastAPI()
    configure_web_security(app, WebSecuritySettings())

    @app.get("/data")
    def data():
        return {"ok": True}

    @app.websocket("/ws")
    async def socket(ws: WebSocket):
        await ws.accept()
        await ws.send_json({"ready": True})
        await ws.close()
    return app


def test_cors_allowed_and_forbidden_origins():
    with TestClient(security_app()) as client:
        headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}
        allowed = client.options("/data", headers=headers)
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == headers["Origin"]
        assert "access-control-allow-credentials" not in allowed.headers
        forbidden = client.options("/data", headers={**headers, "Origin": "https://evil.example"})
        assert forbidden.status_code == 400
        assert "access-control-allow-origin" not in forbidden.headers


def test_hosts_and_security_headers():
    with TestClient(security_app()) as client:
        response = client.get("/data")
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert client.get("/data", headers={"Host": "evil.example"}).status_code == 400


def test_websocket_origin_validation():
    with TestClient(security_app()) as client:
        with client.websocket_connect("/ws", headers={"Origin": "http://localhost:5173"}) as socket:
            assert socket.receive_json()["ready"]
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws", headers={"Origin": "https://evil.example"}):
                pass


@pytest.mark.parametrize("values", [
    {"CORS_ORIGINS": "*"}, {"CORS_ORIGINS": "http://localhost/path"},
    {"TRUSTED_HOSTS": "*"}, {"ENVIRONMENT": "prod"}, {"ENVIRONMENT": "production"},
    {"ENVIRONMENT": "production", "CORS_ORIGINS": "http://example.com", "TRUSTED_HOSTS": "example.com"},
])
def test_rejects_unsafe_settings(values):
    with pytest.raises(ValueError):
        load_web_settings(values)


def test_explicit_production_settings():
    settings = load_web_settings({"ENVIRONMENT": "production", "CORS_ORIGINS": "https://app.example.com", "TRUSTED_HOSTS": "api.example.com", "DATABASE_URL": "postgresql://test", "JWT_SECRET_KEY": "a-random-test-secret-of-at-least-32-characters"})
    assert settings.production
    assert settings.origins == ("https://app.example.com",)
