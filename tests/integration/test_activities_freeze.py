"""Actividades corporales congeladas (ACTIVITIES_ENABLED=false): el Analizador
termina en el resultado de la expresión, no se inician ni se recomiendan
actividades y el catálogo solo se lee. Las reglas se aplican en FastAPI."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import ActivityCatalog, AuthenticationService, IdentityRegistrationService, SessionService
from emotv.config import ACTIVITIES_FROZEN_MESSAGE, LiveExpressionSettings
from emotv.domain import Role, SessionState, User
from emotv.infrastructure.persistence import (Base, PostgresConsentRepository, PostgresSessionRepository,
                                              PostgresStudentRepository, PostgresUserRepository)
from emotv.interfaces.web.activity_router import create_activity_router
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.expression_router import expression_payload
from emotv.interfaces.web.session_router import create_session_router
from tests.integration.test_browser_activity_api import (CATALOG, CLOCK, AdaptiveAnalyzer, Processor, _open_adaptive,
                                                         _recognize, _student_session)


@pytest.fixture
def frozen():
    CLOCK.now = 0.0
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users, students, consents = (PostgresUserRepository(factory), PostgresStudentRepository(factory),
                                 PostgresConsentRepository(factory))
    auth = AuthenticationService(users, "frozen-flow-secret-at-least-32-characters")
    identity = IdentityRegistrationService(users, students, consents, auth)
    user, student = identity.register_student("flow@example.com", "flow-password-123", "code-flow")
    identity.grant_consent(student.id, "test-v1")
    superadmin = users.save(User("sa-flow", "soporte@example.com", auth.hash_password("superadmin-pass-123"),
                                 Role.SUPERADMIN, datetime.now(timezone.utc)))
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
    catalog = ActivityCatalog()
    app = FastAPI()
    app.include_router(create_session_router(sessions, auth, users, students, activities=catalog,
                                             activities_enabled=False))
    app.include_router(create_activity_router(catalog, auth, users, changes_enabled=False))
    app.include_router(create_analysis_router(
        sessions, catalog, auth, users, students, Processor,
        model_admission=lambda model_id: dict(model_id=model_id, state="SUPPORTED", reasons=[]),
        emotion_analyzer_factory=lambda model_id: AdaptiveAnalyzer(),
        adaptive_processor_factory=lambda activity, analyzer, emotion: pytest.fail("no se inicia una actividad"),
        live_settings=LiveExpressionSettings(stable_seconds=1.0, min_confidence=0.5), live_clock=CLOCK,
        expression_info=lambda key: expression_payload(CATALOG.get(key)), activities_enabled=False))
    with TestClient(app) as client:
        yield client, auth, user, superadmin, sessions
    engine.dispose()


def bearer(auth, user):
    return {"Authorization": f"Bearer {auth.create_access_token(user)}"}


def test_el_analizador_termina_en_el_resultado_sin_actividades(frozen):
    client, auth, user, _, sessions = frozen
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json({"type": "authenticate", "token": auth.create_access_token(user), "session_id": session_id})
        ready = socket.receive_json()
        assert ready["state"] == "live" and ready["activities_enabled"] is False
        socket.close()
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        _, result = _recognize(socket)
        assert result["activities_enabled"] is False
        assert result["activity"] is None and result["activities"] == []
        assert result["expression"]["expression_key"] == "sadness"
        # Elegir una actividad se rechaza sin cerrar el análisis.
        socket.send_json({"type": "select_activity", "activity_id": "arms_up_5s"})
        rejected = socket.receive_json()
        assert rejected["type"] == "error" and rejected["message"] == ACTIVITIES_FROZEN_MESSAGE
        socket.send_json({"type": "finish_without_activity"})
        finished = socket.receive_json()
        assert finished["type"] == "completed" and finished["message"] == "Sesión finalizada. Tu expresión quedó registrada."
    final = sessions.get_session(session_id)
    assert final.state is SessionState.COMPLETED and final.activity_id is None and final.initial_emotion == "sadness"


def test_no_se_inicia_una_sesion_con_actividad(frozen):
    client, auth, user, _, _ = frozen
    response = client.post("/sessions", headers=bearer(auth, user), json={
        "session_type": "propia", "authorization_confirmed": True, "activity_id": "arms_up_5s"})
    assert response.status_code == 403 and response.json()["detail"] == ACTIVITIES_FROZEN_MESSAGE


def test_el_catalogo_se_lee_pero_no_se_cambia(frozen):
    client, auth, _, superadmin, _ = frozen
    headers = bearer(auth, superadmin)
    listed = client.get("/activities", headers=headers)
    assert listed.status_code == 200 and listed.json()
    assert client.delete("/activities/arms_up_5s", headers=headers).status_code == 403
    assert client.get("/activities/arms_up_5s", headers=headers).status_code == 200
