from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import ActivityCatalog, AuthenticationService, SessionService
from emotv.domain import User, Role
from emotv.infrastructure.persistence.models import Base
from emotv.infrastructure.persistence import PostgresUserRepository, PostgresStudentRepository, PostgresConsentRepository, PostgresSessionRepository
from emotv.infrastructure.persistence.postgres_activity_repository import PostgresActivityRepository
from emotv.interfaces.web.identity_router import create_identity_router
from emotv.interfaces.web.activity_router import create_activity_router
from emotv.interfaces.web.session_router import create_session_router
from emotv.interfaces.web.analysis_router import create_analysis_router


def test_identity_activity_and_session_api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users = PostgresUserRepository(factory)
    students = PostgresStudentRepository(factory)
    consents = PostgresConsentRepository(factory)
    auth = AuthenticationService(users, "isolated-api-test-secret-at-least-32-characters")
    admin = users.save(User("admin", "admin@example.com", auth.hash_password("admin-password-123"), Role.ADMIN, datetime.now(timezone.utc)))
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
    catalog = ActivityCatalog(repository=PostgresActivityRepository(factory))
    app = FastAPI()
    app.include_router(create_identity_router(auth, users, students, consents))
    app.include_router(create_activity_router(catalog, auth, users))
    app.include_router(create_session_router(sessions, auth, users, students, activities=catalog))
    app.include_router(create_analysis_router(sessions, catalog, auth, users, students, lambda activity: None))
    headers = {"Authorization": f"Bearer {auth.create_access_token(admin)}"}
    with TestClient(app) as client:
        assert client.get("/students").status_code == 401
        with client.websocket_connect("/ws/activity") as socket:
            socket.send_json({"type": "authenticate", "token": "invalid"})
            assert socket.receive_json()["type"] == "error"
        created = client.post("/users", headers=headers, json=dict(email="student@example.com", password="student-password-123", role="student", student_code="2026-01"))
        assert created.status_code == 201
        assert "password_hash" not in created.json()
        student_user = users.get_by_id(created.json()["id"])
        own = {"Authorization": f"Bearer {auth.create_access_token(student_user)}"}
        student_id = client.get("/students", headers=own).json()[0]["id"]
        assert client.get("/users", headers=own).status_code == 403
        assert client.get(f"/students/{student_id}", headers=headers).status_code == 200
        assert client.get(f"/students/{student_id}/consents/active", headers=own).json() is None
        assert client.post("/sessions", headers=own, json={}).status_code == 403
        assert client.post(f"/students/{student_id}/consents", headers=own, json={"policy_version": "v1"}).status_code == 201
        assert client.post(f"/students/{student_id}/consents", headers=own, json={"policy_version": "v1"}).status_code == 409
        activity = dict(id="test", name="Prueba", description="Brazos arriba", required_posture="arms_up", duration_seconds=1, repetitions=1)
        assert client.post("/activities", headers=headers, json=activity).status_code == 201
        assert ActivityCatalog(repository=PostgresActivityRepository(factory)).get("test").name == "Prueba"
        assert client.post("/activities", headers=headers, json=activity).status_code == 409
        session = client.post("/sessions", headers=own, json={"activity_id": "test"}).json()
        result = dict(initial_emotion="neutral", emotion_confidence=0.9, activity_id="test", exercise_result="completed", exercise_duration_seconds=1)
        url = f"/sessions/{session['id']}/complete"
        assert client.post(url, headers=own, json=result).status_code == 403
        assert client.post(url, headers=headers, json=result).status_code == 200
        assert client.post(url, headers=headers, json=result).status_code == 409
        assert client.post(f"/students/{student_id}/consents/revoke", headers=own).status_code == 200
        assert client.post("/sessions", headers=own, json={}).status_code == 403
        assert client.patch(f"/users/{student_user.id}", headers=headers, json={"is_active": False}).status_code == 200
        assert client.get("/students", headers=own).status_code == 401
        assert client.delete("/users/admin", headers=headers).status_code == 409
    engine.dispose()


def test_legacy_camera_requires_authentication(monkeypatch):
    import importlib
    from starlette.websockets import WebSocketDisconnect
    import pytest
    module = importlib.import_module("emotv.interfaces.web.app")
    with TestClient(module.app) as client:
        for path in ("/video_feed", "/emotion", "/stats", "/control?action=start"):
            assert client.get(path).status_code == 401
        assert client.post("/control/start").status_code == 401
        with client.websocket_connect("/ws/emotions") as socket:
            socket.send_json({"type": "authenticate", "token": "invalid"})
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()
