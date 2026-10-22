"""Modelo local predeterminado: elección del superadministrador, respaldo y sesiones.

SQLite en memoria, admisión controlada por la prueba y analizadores falsos: no
se cargan pesos reales ni se llama a servicios externos.
"""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import ActivityCatalog, AuthenticationService, IdentityRegistrationService, SessionService
from emotv.application.local_model_service import FERPLUS_MODEL_ID, HSEMOTION_MODEL_ID, LocalModelService
from emotv.config import LiveExpressionSettings
from emotv.domain import Role, SessionType, User
from emotv.infrastructure.persistence import (
    Base,
    PostgresConsentRepository,
    PostgresLocalModelSettingsRepository,
    PostgresSessionRepository,
    PostgresStudentRepository,
    PostgresUserRepository,
)
from emotv.infrastructure.vision.emotion_classifier import ClassifierCache
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.model_admin_router import create_model_admin_router
from emotv.interfaces.web.session_router import create_session_router


class FakeAnalyzer:
    def __init__(self, classifier):
        self.classifier = classifier

    def analyze(self, frame):
        return "neutral", .9


class Env:
    def __init__(self, client, auth, users, sessions, settings, states, loads, admin, student_user, other_user):
        self.client, self.auth, self.users, self.sessions = client, auth, users, sessions
        self.settings, self.states, self.loads = settings, states, loads
        self.admin, self.student_user, self.other_user = admin, student_user, other_user

    def headers(self, user):
        return {"Authorization": f"Bearer {self.auth.create_access_token(user)}"}

    def open_session(self, user, model_id=None):
        """Crea una sesión propia, abre el analizador y devuelve el primer mensaje."""
        response = self.client.post("/sessions", headers=self.headers(user), json={})
        assert response.status_code == 201
        session_id = response.json()["id"]
        message = {"type": "authenticate", "token": self.auth.create_access_token(user), "session_id": session_id}
        if model_id is not None:
            message["emotion_model_id"] = model_id
        with self.client.websocket_connect("/ws/activity") as socket:
            socket.send_json(message)
            first = socket.receive_json()
        return session_id, first


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users, students, consents = PostgresUserRepository(factory), PostgresStudentRepository(factory), PostgresConsentRepository(factory)
    auth = AuthenticationService(users, "local-models-secret-at-least-32-characters")
    identity = IdentityRegistrationService(users, students, consents, auth)
    student_user, student = identity.register_student("a@example.com", "a-password-123", "code-a")
    other_user, other = identity.register_student("b@example.com", "b-password-123", "code-b")
    identity.grant_consent(student.id, "test-v1")
    identity.grant_consent(other.id, "test-v1")
    admin = users.save(User("admin-models", "superadmin@example.com", auth.hash_password("admin-password-123"),
                            Role.SUPERADMIN, datetime.now(timezone.utc)))
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
    states = {HSEMOTION_MODEL_ID: "SUPPORTED", FERPLUS_MODEL_ID: "SUPPORTED", "hardlyhumans_vit": "BLOCKED"}

    def admission(model_id):
        state = states[model_id]
        return dict(model_id=model_id, state=state, reasons=["Benchmark vencido"] if state == "BLOCKED" else [],
                    checks=dict(weights_verified=True, benchmark_current=state != "BLOCKED"),
                    metrics=dict(p95_ms=40.0, concurrent_frame_p95_ms={"1": 45.0, "2": 70.0}))

    settings = PostgresLocalModelSettingsRepository(factory)
    local_models = LocalModelService(settings, admission)
    loads = []

    def load(model_id):
        loads.append(model_id)
        return object()

    classifiers = ClassifierCache(load)
    app = FastAPI()
    app.include_router(create_session_router(sessions, auth, users, students, activities=ActivityCatalog()))
    app.include_router(create_model_admin_router(local_models, auth, users))
    app.include_router(create_analysis_router(
        sessions, ActivityCatalog(), auth, users, students, lambda activity: None,
        model_admission=admission,
        emotion_analyzer_factory=lambda model_id: FakeAnalyzer(classifiers.get(model_id)),
        adaptive_processor_factory=lambda activity, analyzer, emotion: None,
        live_settings=LiveExpressionSettings(stable_seconds=1.0, min_confidence=0.5),
        local_models=local_models,
    ))
    with TestClient(app) as client:
        yield Env(client, auth, users, sessions, settings, states, loads, admin, student_user, other_user)
    engine.dispose()


def test_default_change_applies_without_restart_and_classifiers_are_reused(env):
    _, first = env.open_session(env.student_user)
    assert first["type"] == "ready" and first["emotion_model_id"] == HSEMOTION_MODEL_ID

    response = env.client.put("/admin/models/default", headers=env.headers(env.admin),
                              json={"model_id": FERPLUS_MODEL_ID})
    assert response.status_code == 200 and response.json()["default_model_id"] == FERPLUS_MODEL_ID
    session_id, second = env.open_session(env.student_user)
    assert second["emotion_model_id"] == FERPLUS_MODEL_ID
    assert env.sessions.get_session(session_id).emotion_model_id == FERPLUS_MODEL_ID

    env.client.put("/admin/models/default", headers=env.headers(env.admin), json={"model_id": HSEMOTION_MODEL_ID})
    _, third = env.open_session(env.other_user)
    assert third["emotion_model_id"] == HSEMOTION_MODEL_ID
    # Tres sesiones, dos modelos: cada clasificador se cargó una sola vez.
    assert env.loads == [HSEMOTION_MODEL_ID, FERPLUS_MODEL_ID]


def test_model_without_admission_cannot_be_chosen_as_default(env):
    env.states[FERPLUS_MODEL_ID] = "BLOCKED"
    response = env.client.put("/admin/models/default", headers=env.headers(env.admin),
                              json={"model_id": FERPLUS_MODEL_ID})
    assert response.status_code == 409
    assert "Benchmark vencido" in response.json()["detail"]
    assert env.settings.get() is None  # sigue el predeterminado inicial
    assert env.client.put("/admin/models/default", headers=env.headers(env.admin),
                          json={"model_id": "hardlyhumans_vit"}).status_code == 422


def test_session_rejects_a_requested_model_without_admission(env):
    env.states[FERPLUS_MODEL_ID] = "BLOCKED"
    session_id, message = env.open_session(env.student_user, FERPLUS_MODEL_ID)
    assert message["type"] == "error" and message["admission"]["model_id"] == FERPLUS_MODEL_ID
    assert env.sessions.get_session(session_id).emotion_model_id is None
    assert env.loads == []


def test_default_losing_admission_uses_the_backup_and_records_it(env):
    env.client.put("/admin/models/default", headers=env.headers(env.admin), json={"model_id": HSEMOTION_MODEL_ID})
    env.states[HSEMOTION_MODEL_ID] = "BLOCKED"
    session_id, message = env.open_session(env.student_user)
    assert message["type"] == "ready" and message["emotion_model_id"] == FERPLUS_MODEL_ID
    assert env.sessions.get_session(session_id).emotion_model_id == FERPLUS_MODEL_ID

    stored = env.settings.get()
    assert stored.default_model_id == HSEMOTION_MODEL_ID  # la elección del superadministrador se conserva
    assert stored.fallback_model_id == FERPLUS_MODEL_ID and stored.fallback_at is not None
    body = env.client.get("/admin/models", headers=env.headers(env.admin)).json()
    assert body["fallback_model_id"] == FERPLUS_MODEL_ID


def test_without_any_admitted_model_the_session_is_blocked(env):
    env.states[HSEMOTION_MODEL_ID] = env.states[FERPLUS_MODEL_ID] = "BLOCKED"
    session_id, message = env.open_session(env.student_user)
    assert message["type"] == "error"
    assert env.sessions.get_session(session_id).emotion_model_id is None
    assert env.settings.get() is None  # sin respaldo usado no hay nada que registrar


def test_a_user_choice_does_not_change_other_sessions(env):
    chosen_id, chosen = env.open_session(env.student_user, FERPLUS_MODEL_ID)
    other_id, other = env.open_session(env.other_user)
    assert chosen["emotion_model_id"] == FERPLUS_MODEL_ID
    assert other["emotion_model_id"] == HSEMOTION_MODEL_ID
    assert env.sessions.get_session(chosen_id).emotion_model_id == FERPLUS_MODEL_ID
    assert env.sessions.get_session(other_id).emotion_model_id == HSEMOTION_MODEL_ID
    assert env.settings.get() is None  # probar un modelo no toca la configuración


def test_conductor_sees_local_models_without_operational_details(env):
    env.states[FERPLUS_MODEL_ID] = "BLOCKED"
    models = env.client.get("/analysis/models", headers=env.headers(env.student_user)).json()
    assert models == [
        {"model_id": HSEMOTION_MODEL_ID, "state": "SUPPORTED", "is_default": True},
        {"model_id": FERPLUS_MODEL_ID, "state": "BLOCKED", "is_default": False},
    ]
    _, message = env.open_session(env.student_user, "hardlyhumans_vit")
    assert message["type"] == "error" and message["code"] == 4403


def test_only_the_superadmin_reads_or_changes_the_configuration(env):
    psychologist = env.users.save(User("psy-models", "docente@example.com", env.auth.hash_password("psy-password-123"),
                                       Role.PSYCHOLOGIST, datetime.now(timezone.utc)))
    assert env.client.get("/admin/models").status_code == 401
    for user in (env.student_user, psychologist):
        assert env.client.get("/admin/models", headers=env.headers(user)).status_code == 403
        assert env.client.put("/admin/models/default", headers=env.headers(user),
                              json={"model_id": FERPLUS_MODEL_ID}).status_code == 403
    assert env.settings.get() is None


def test_models_page_reports_checks_and_who_changed_the_default(env):
    env.client.put("/admin/models/default", headers=env.headers(env.admin), json={"model_id": FERPLUS_MODEL_ID})
    body = env.client.get("/admin/models", headers=env.headers(env.admin)).json()
    assert body["default_model_id"] == FERPLUS_MODEL_ID
    assert body["changed_by"] == "superadmin@example.com" and body["changed_at"]
    by_id = {item["model_id"]: item for item in body["models"]}
    assert set(by_id) == {HSEMOTION_MODEL_ID, FERPLUS_MODEL_ID}
    assert by_id[FERPLUS_MODEL_ID]["is_default"] and not by_id[HSEMOTION_MODEL_ID]["is_default"]
    assert by_id[FERPLUS_MODEL_ID]["checks"] == {"weights_verified": True, "benchmark_current": True}
    assert by_id[FERPLUS_MODEL_ID]["p95_ms"] == 40.0
    assert by_id[FERPLUS_MODEL_ID]["concurrent_frame_p95_ms"] == {"1": 45.0, "2": 70.0}


def test_sessions_store_their_type(env):
    response = env.client.post("/sessions", headers=env.headers(env.student_user), json={})
    assert response.json()["session_type"] == "propia"
    assert env.sessions.get_session(response.json()["id"]).session_type is SessionType.OWN
    for session_type in ("participante_adulto", "participante_infantil"):
        # Sin un participante registrado con su autorización firmada no se inician.
        rejected = env.client.post("/sessions", headers=env.headers(env.student_user),
                                   json={"session_type": session_type})
        assert rejected.status_code == 422
    assert env.client.post("/sessions", headers=env.headers(env.student_user),
                           json={"session_type": "otro"}).status_code == 422


def test_the_repository_keeps_every_session_type(env):
    for session_type in SessionType:
        created = env.sessions.create_session(session_type=session_type)
        assert env.sessions.get_session(created.id).session_type is session_type
