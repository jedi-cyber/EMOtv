"""Recomendaciones configurables en base de datos y recomendador tolerante."""
from __future__ import annotations

import importlib.util
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import (
    DEFAULT_ACTIVITIES,
    DEFAULT_ACTIVITIES_BY_EMOTION,
    ActivityCatalog,
    AuthenticationService,
    IdentityRegistrationService,
    SessionService,
)
from emotv.application.expression_catalog_service import ExpressionCatalogService
from emotv.application.recommendation_config_service import RecommendationConfigService
from emotv.domain import Role, SessionState, User
from emotv.domain.expression_info import EXPRESSION_KEYS
from emotv.config import LiveExpressionSettings
from emotv.infrastructure.persistence import (
    Base,
    PostgresActivityRepository,
    PostgresConsentRepository,
    PostgresExpressionInfoRepository,
    PostgresRecommendationRepository,
    PostgresSessionRepository,
    PostgresStudentRepository,
    PostgresUserRepository,
)
from emotv.interfaces.web.activity_router import create_activity_router
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.recommendation_router import create_recommendation_router
from emotv.interfaces.web.session_router import create_session_router
from tests.integration.test_browser_activity_api import (
    CLOCK, JPEG, AdaptiveAnalyzer, AdaptiveProcessor, Processor, _open_adaptive, _recognize, _student_session,
)
from tests.integration.test_expressions_api import seeded_items

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261009_13_emotion_activity_recommendations.py"
ROUTER_LOGGER = "emotv.interfaces.web.analysis_router"
RECOMMENDER_LOGGER = "emotv.application.activity_recommendation_service"


@pytest.fixture
def env():
    CLOCK.now = 0.0
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _):  # ON DELETE CASCADE como en PostgreSQL
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    expressions = PostgresExpressionInfoRepository(factory)
    for item in seeded_items():
        expressions.save(item)
    activity_repository = PostgresActivityRepository(factory)
    for activity in DEFAULT_ACTIVITIES:
        activity_repository.add(activity)
    recommendations = PostgresRecommendationRepository(factory)
    for key, ids in DEFAULT_ACTIVITIES_BY_EMOTION.items():
        recommendations.replace(key, ids)
    catalog = ActivityCatalog(repository=activity_repository)
    config = RecommendationConfigService(recommendations, catalog)

    users, students, consents = PostgresUserRepository(factory), PostgresStudentRepository(factory), PostgresConsentRepository(factory)
    auth = AuthenticationService(users, "recommendations-secret-at-least-32-chars")
    identity = IdentityRegistrationService(users, students, consents, auth)
    student_user, student = identity.register_student("rec@example.com", "rec-password-1234", "code-rec")
    identity.grant_consent(student.id, "test-v1")
    admin = users.save(User("admin-rec", "admin-rec@example.com", auth.hash_password("admin-password-123"),
                            Role.ADMIN, datetime.now(timezone.utc)))
    psychologist = users.save(User("psy-rec", "psy-rec@example.com", auth.hash_password("psy-password-1234"),
                                   Role.PSYCHOLOGIST, datetime.now(timezone.utc)))
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
    labels = ExpressionCatalogService(expressions)
    state = {"processor_error": None, "analyzer_error": None}

    class Analyzer(AdaptiveAnalyzer):
        def analyze_detailed(self, frame):
            if state["analyzer_error"]:
                raise state["analyzer_error"]
            return super().analyze_detailed(frame)

    def adaptive_processor(activity, analyzer, emotion):
        if state["processor_error"]:
            raise state["processor_error"]
        return AdaptiveProcessor(activity, emotion)

    app = FastAPI()
    app.include_router(create_activity_router(catalog, auth, users, recommendations=config,
                                              expression_label=lambda key: labels.get(key).label_es))
    app.include_router(create_recommendation_router(config, auth, users))
    app.include_router(create_session_router(sessions, auth, users, students, activities=catalog))
    app.include_router(create_analysis_router(
        sessions, catalog, auth, users, students, Processor,
        emotion_analyzer_factory=lambda model_id: Analyzer(),
        adaptive_processor_factory=adaptive_processor,
        live_settings=LiveExpressionSettings(stable_seconds=1.0, min_confidence=0.5),
        live_clock=CLOCK,
        recommendations=recommendations,
    ))
    headers = {name: {"Authorization": f"Bearer {auth.create_access_token(account)}"}
               for name, account in (("admin", admin), ("student", student_user), ("psychologist", psychologist))}
    with TestClient(app) as client:
        yield dict(client=client, auth=auth, student_user=student_user, student=student, sessions=sessions,
                   recommendations=recommendations, headers=headers, state=state, catalog=catalog)
    engine.dispose()


def recognize_sadness(env, **extra):
    """Abre el análisis del estudiante (el analizador falso estima tristeza) y registra."""
    session_id = _student_session(env["client"], env["auth"], env["student_user"])
    socket_cm = env["client"].websocket_connect("/ws/activity")
    socket = socket_cm.__enter__()
    _open_adaptive(env["client"], env["auth"], env["student_user"], session_id, socket)
    _, recommendation = _recognize(socket, **extra)
    return session_id, socket_cm, socket, recommendation


def activity_body(activity_id, steps):
    return {"id": activity_id, "name": "Actividad editada", "description": "Descripción editada",
            "required_posture": steps[0]["posture"], "duration_seconds": 4, "repetitions": 1, "steps": steps}


ONE_STEP = [{"posture": "arms_up", "instruction": "Eleva los brazos", "duration_seconds": 4}]
TWO_STEPS = ONE_STEP + [{"posture": "arms_open", "instruction": "Abre los brazos", "duration_seconds": 4}]


# --- Semilla de la migración ---------------------------------------------------------

def test_migration_seed_matches_previous_code_associations():
    spec = importlib.util.spec_from_file_location("recommendations_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SEED == dict(DEFAULT_ACTIVITIES_BY_EMOTION)
    assert set(module.SEED) == set(EXPRESSION_KEYS)


# --- Recomendador tolerante en el WebSocket -----------------------------------------

def test_single_step_activity_is_filtered_without_breaking_the_session(env, caplog):
    # Dato heredado o escrito fuera de la API: una asociación a una actividad de un paso.
    env["recommendations"].replace("sadness", ("arms_up_5s", "open_and_reach"))
    with caplog.at_level(logging.WARNING, logger=RECOMMENDER_LOGGER):
        session_id, socket_cm, socket, recommendation = recognize_sadness(env)
    try:
        assert recommendation["activity"]["id"] == "open_and_reach"
        assert any("arms_up_5s" in record.getMessage() for record in caplog.records)
        assert env["sessions"].get_session(session_id).state is SessionState.RECOGNIZED
    finally:
        socket_cm.__exit__(None, None, None)


def test_expression_without_valid_candidates_gets_none_and_can_finish(env, caplog):
    env["recommendations"].replace("sadness", ("arms_up_5s",))
    with caplog.at_level(logging.WARNING, logger=RECOMMENDER_LOGGER):
        session_id, socket_cm, socket, recommendation = recognize_sadness(env)
    try:
        assert recommendation["activity"] is None
        assert recommendation["activities"]  # El frontend ofrece la lista de alternativas.
        socket.send_json({"type": "finish_without_activity"})
        assert socket.receive_json()["exercise_result"] == "skipped"
    finally:
        socket_cm.__exit__(None, None, None)
    assert env["sessions"].get_session(session_id).state is SessionState.COMPLETED


def test_variation_uses_the_students_session_history(env):
    sessions = env["sessions"]
    previous = sessions.start_session(student_id=env["student"].id)
    sessions.record_recognition(previous.id, "sadness", .9, "ferplus_onnx", "1.0")
    sessions.assign_activity(previous.id, "morning_mobility")
    sessions.cancel_session(previous.id)
    for _ in range(3):
        _, socket_cm, socket, recommendation = recognize_sadness(env)
        socket_cm.__exit__(None, None, None)
        assert recommendation["activity"]["id"] == "open_and_reach"


# --- Administración de asociaciones ----------------------------------------------------

@pytest.mark.parametrize("role", ["student", "psychologist"])
def test_only_admin_manages_recommendations(env, role):
    client, headers = env["client"], env["headers"]
    assert client.get("/recommendations").status_code == 401
    assert client.get("/recommendations", headers=headers[role]).status_code == 403
    assert client.put("/recommendations/sadness", headers=headers[role],
                      json={"activity_ids": ["full_body_flow"]}).status_code == 403


def test_admin_lists_every_expression(env):
    response = env["client"].get("/recommendations", headers=env["headers"]["admin"])
    assert response.status_code == 200
    items = {item["expression_key"]: item["activity_ids"] for item in response.json()}
    assert list(items) == list(EXPRESSION_KEYS)
    assert items["sadness"] == ["morning_mobility", "open_and_reach"]


def test_admin_edits_are_used_by_the_next_recommendation(env):
    client, admin = env["client"], env["headers"]["admin"]
    response = client.put("/recommendations/sadness", headers=admin, json={"activity_ids": ["full_body_flow"]})
    assert response.status_code == 200
    assert response.json() == {"expression_key": "sadness", "activity_ids": ["full_body_flow"]}
    _, socket_cm, _, recommendation = recognize_sadness(env)
    socket_cm.__exit__(None, None, None)
    assert recommendation["activity"]["id"] == "full_body_flow"

    assert client.put("/recommendations/sadness", headers=admin, json={"activity_ids": []}).status_code == 200
    _, socket_cm, _, recommendation = recognize_sadness(env)
    socket_cm.__exit__(None, None, None)
    assert recommendation["activity"] is None


def test_priority_follows_the_submitted_order(env):
    client, admin = env["client"], env["headers"]["admin"]
    client.put("/recommendations/fear", headers=admin, json={"activity_ids": ["balanced_postures", "morning_mobility"]})
    assert client.get("/recommendations/fear", headers=admin).json()["activity_ids"] == ["balanced_postures", "morning_mobility"]


@pytest.mark.parametrize("activity_ids, fragment", [
    (["missing"], "no existe"),
    (["arms_up_5s"], "al menos 2"),
    (["morning_mobility", "morning_mobility"], "repetidas"),
])
def test_invalid_association_is_rejected(env, activity_ids, fragment):
    response = env["client"].put("/recommendations/sadness", headers=env["headers"]["admin"],
                                 json={"activity_ids": activity_ids})
    assert response.status_code == 422
    assert fragment in response.json()["detail"]
    assert env["recommendations"].activity_ids_for("sadness") == ("morning_mobility", "open_and_reach")


def test_unknown_expression_returns_404(env):
    admin = env["headers"]["admin"]
    assert env["client"].put("/recommendations/joy", headers=admin, json={"activity_ids": []}).status_code == 404
    assert env["client"].get("/recommendations/joy", headers=admin).status_code == 404


# --- Validación al editar actividades -------------------------------------------------

def test_editing_a_recommended_activity_to_one_step_returns_409_naming_expressions(env):
    response = env["client"].put("/activities/morning_mobility", headers=env["headers"]["admin"],
                                 json=activity_body("morning_mobility", ONE_STEP))
    assert response.status_code == 409
    detail = response.json()["detail"]
    for label in ("Tristeza", "Neutral", "Desagrado", "Miedo"):
        assert label in detail
    assert len(env["catalog"].get("morning_mobility").steps) == 3


def test_other_activity_edits_still_work(env):
    client, admin = env["client"], env["headers"]["admin"]
    assert client.put("/activities/morning_mobility", headers=admin,
                      json=activity_body("morning_mobility", TWO_STEPS)).status_code == 200
    # arms_up_5s no está recomendada: puede quedar con un paso.
    assert client.put("/activities/arms_up_5s", headers=admin,
                      json=activity_body("arms_up_5s", ONE_STEP)).status_code == 200


def test_deleting_an_activity_removes_its_associations(env):
    client, admin = env["client"], env["headers"]["admin"]
    assert client.delete("/activities/open_and_reach", headers=admin).status_code == 204
    assert "open_and_reach" not in env["recommendations"].activity_ids_for("sadness")
    assert env["recommendations"].expressions_using("open_and_reach") == ()


# --- Errores por etapa ---------------------------------------------------------------------

def test_activity_stage_failure_is_logged_and_reported_keeping_the_expression(env, caplog):
    env["state"]["processor_error"] = RuntimeError("pose landmarker no disponible")
    with caplog.at_level(logging.ERROR, logger=ROUTER_LOGGER):
        session_id, socket_cm, socket, recommendation = recognize_sadness(env)
        try:
            socket.send_json({"type": "select_activity", "activity_id": recommendation["activity"]["id"]})
            error = socket.receive_json()
        finally:
            socket_cm.__exit__(None, None, None)
    assert error["type"] == "error" and error["stage"] == "activity"
    assert "actividad" in error["message"]
    record = next(item for item in caplog.records if "activity" in item.getMessage())
    assert record.exc_info and "pose landmarker" in str(record.exc_info[1])
    stored = env["sessions"].get_session(session_id)
    assert stored.initial_emotion == "sadness"
    assert stored.exercise_result == "cancelled"


def test_recognition_stage_failure_is_reported(env, caplog):
    env["state"]["analyzer_error"] = RuntimeError("fallo del clasificador")
    session_id = _student_session(env["client"], env["auth"], env["student_user"])
    with caplog.at_level(logging.ERROR, logger=ROUTER_LOGGER):
        with env["client"].websocket_connect("/ws/activity") as socket:
            _open_adaptive(env["client"], env["auth"], env["student_user"], session_id, socket)
            socket.send_bytes(JPEG)
            error = socket.receive_json()
    assert error["stage"] == "recognition" and "reconocimiento" in error["message"]
    # El log lleva etapa y sesión, nunca bytes de la imagen.
    assert all(JPEG[:16] not in record.getMessage().encode("latin-1", "ignore") for record in caplog.records)
    assert any(session_id in record.getMessage() for record in caplog.records)
