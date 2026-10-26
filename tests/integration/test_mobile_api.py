"""API del aplicativo móvil: inicio de sesión, tokens revocables, resumen, sesión
con o sin protocolo desde el dispositivo (sin participantes), URLs firmadas e
HTTPS (SQLite en memoria, analizador falso, sin modelos ni imágenes de personas)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from emotv.application.login_throttle import LoginThrottle
from emotv.application.mobile_auth_service import MobileAuthService
from emotv.application.signed_urls import StimulusUrlSigner
from emotv.config import LoginLimits
from emotv.domain.guided_session import FrameAssessment, QualityIssue
from emotv.infrastructure.persistence import PostgresLoginAttemptRepository, PostgresMobileSessionRepository
from emotv.infrastructure.persistence.models import Base
from emotv.interfaces.web.mobile_router import create_mobile_router
from emotv.interfaces.web.security import configure_web_security, load_web_settings
from emotv.interfaces.web.session_router import create_session_starter
from emotv.application.commitment_service import load_text
from tests.integration.test_guided_sessions import step, stimuli
from tests.integration.test_privacy_accounts import KEY, accept_commitment, audit_actions, env, headers  # noqa: F401
from tests.integration.test_questionnaires import create as create_questionnaire

PASSWORDS = {"usuario1@example.com": "usuario-1-pass-123", "usuario2@example.com": "usuario-2-pass-123",
             "docente.a@example.com": "docente-a-pass-123", "facultad@example.com": "admin-password-123",
             "soporte@example.com": "superadmin-pass-123"}
# Bytes reconocibles: si el cuadro se guardara en algún lado, la prueba lo encontraría.
FRAME = b"\xff\xd8\xff\xe0MARCA-DEL-CUADRO-MOVIL\xff\xd9"
# Nada de resultados: ni la expresión estimada (el analizador falso devuelve "happiness") ni sus campos.
RESULT_WORDS = ("happiness", "neutral", "confidence", "distribution", "probab", "captures", "'emotion'")


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def build(env, *, production: bool = False, base_url: str = "http://testserver"):  # noqa: F811
    signer_clock = Clock(datetime.now(timezone.utc))
    signer = StimulusUrlSigner("firma-de-prueba-con-mas-de-32-caracteres", signer_clock)
    throttle = LoginThrottle(PostgresLoginAttemptRepository(env.factory), LoginLimits(3, 50, 15))
    service = MobileAuthService(PostgresMobileSessionRepository(env.factory), env.auth, env.users, env.audit,
                                throttle, clock=env.clock)
    app = FastAPI()
    configure_web_security(app, load_web_settings({"ENVIRONMENT": "test"}))
    app.include_router(create_mobile_router(
        service, env.users, audit=env.audit, sessions=env.sessions,
        start_session=create_session_starter(env.sessions, env.students, env.authorization, None, env.commitments,
                                             env.protocols, env.questionnaires, env.audit),
        protocols=env.protocols, questionnaires=env.questionnaires,
        guided=env.guided, signer=signer,
        stimulus_image=env.stimuli.repository.get_image, decode_frame=lambda data: data or None,
        production=production, api_version="1.0.0rc1", min_app_version="1.2.0", clock=env.clock))
    return SimpleNamespace(client=TestClient(app, base_url=base_url), service=service, signer=signer,
                           signer_clock=signer_clock)


@pytest.fixture
def mobile(env):  # noqa: F811
    built = build(env)
    with built.client:
        yield built


def login(mobile, email, password=None):
    return mobile.client.post("/mobile/auth/login", json={"email": email, "password": password or PASSWORDS[email]})


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def signed_in(mobile, email):
    response = login(mobile, email)
    assert response.status_code == 200, response.text
    return response.json()


def error_code(response):
    return response.json()["detail"]["code"]


# --- Estado e inicio de sesión ----------------------------------------------------------

def test_status_reports_versions_without_login(mobile):
    body = mobile.client.get("/mobile/status").json()
    assert body["status"] == "ok" and body["api_version"] == "1.0.0rc1" and body["min_app_version"] == "1.2.0"
    assert body["services"] == {"login": True, "sessions": True}


@pytest.mark.parametrize("email", ["facultad@example.com", "soporte@example.com"])
def test_management_roles_cannot_sign_in_on_mobile(env, mobile, email):  # noqa: F811
    response = login(mobile, email)
    assert response.status_code == 403 and error_code(response) == "role_not_allowed"
    assert "access_token" not in response.text
    assert ("login", "mobile_session", "denied") in audit_actions(env)


def test_users_and_docentes_sign_in_and_tokens_are_short_lived(env, mobile):  # noqa: F811
    for email in ("usuario1@example.com", "docente.a@example.com"):
        tokens = signed_in(mobile, email)
        assert tokens["token_type"] == "bearer" and tokens["expires_in"] == 15 * 60
        assert tokens["refresh_expires_in"] == 30 * 24 * 60 * 60
        assert tokens["user"]["role_name"] in ("Usuario", "Docente")
    assert audit_actions(env).count(("login", "mobile_session", "success")) == 2


def test_wrong_password_is_rejected_and_repeated_failures_are_blocked(mobile):
    for _ in range(3):
        failed = login(mobile, "usuario1@example.com", "incorrecta-123456")
        assert failed.status_code == 401 and error_code(failed) == "invalid_credentials"
    blocked = login(mobile, "usuario1@example.com")
    assert blocked.status_code == 429 and error_code(blocked) == "too_many_attempts"
    assert blocked.headers["Retry-After"] == str(15 * 60)


def test_a_provisional_password_must_be_changed_on_the_web_first(env, mobile):  # noqa: F811
    env.users.save(replace(env.user_2, must_change_password=True))
    response = login(mobile, "usuario2@example.com")
    assert response.status_code == 403 and error_code(response) == "password_change_required"


def test_mobile_and_web_tokens_are_not_interchangeable(env, mobile):  # noqa: F811
    tokens = signed_in(mobile, "usuario1@example.com")
    assert env.client.get("/auth/me", headers=bearer(tokens)).status_code == 401
    web = mobile.client.get("/mobile/summary", headers=headers(env, env.user_1))
    assert web.status_code == 401 and error_code(web) == "invalid_token"


def test_logout_revokes_the_refresh_token_and_the_access_token(env, mobile):  # noqa: F811
    tokens = signed_in(mobile, "usuario1@example.com")
    assert mobile.client.get("/mobile/summary", headers=bearer(tokens)).status_code == 200
    assert mobile.client.post("/mobile/auth/logout", headers=bearer(tokens)).status_code == 204
    assert mobile.client.get("/mobile/summary", headers=bearer(tokens)).status_code == 401
    refreshed = mobile.client.post("/mobile/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 401 and error_code(refreshed) == "invalid_refresh_token"
    assert ("logout", "mobile_session", "success") in audit_actions(env)


def test_refresh_rotates_and_reusing_an_old_token_revokes_the_session(mobile):
    first = signed_in(mobile, "usuario1@example.com")
    second = mobile.client.post("/mobile/auth/refresh", json={"refresh_token": first["refresh_token"]}).json()
    assert second["refresh_token"] != first["refresh_token"]
    assert mobile.client.get("/mobile/summary", headers=bearer(second)).status_code == 200
    # Alguien reutiliza el token reemplazado: la sesión completa queda revocada.
    reused = mobile.client.post("/mobile/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reused.status_code == 401
    assert mobile.client.get("/mobile/summary", headers=bearer(second)).status_code == 401
    assert mobile.client.post("/mobile/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_changing_the_password_or_deactivating_the_account_invalidates_mobile_tokens(env, mobile):  # noqa: F811
    tokens = signed_in(mobile, "usuario1@example.com")
    env.users.save(replace(env.users.get_by_id(env.user_1.id), token_version=env.user_1.token_version + 1))
    assert mobile.client.get("/mobile/summary", headers=bearer(tokens)).status_code == 401
    assert mobile.client.post("/mobile/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    tokens = signed_in(mobile, "docente.a@example.com")
    env.users.save(replace(env.docente_a, is_active=False))
    assert mobile.client.get("/mobile/summary", headers=bearer(tokens)).status_code == 401


def test_login_does_not_log_the_request_body(mobile, caplog):
    with caplog.at_level(logging.DEBUG):
        login(mobile, "usuario1@example.com")
        login(mobile, "usuario1@example.com", "otra-clave-secreta-999")
    assert "usuario-1-pass-123" not in caplog.text and "otra-clave-secreta-999" not in caplog.text


# --- Resumen del dashboard --------------------------------------------------------------

CONFIRMED = {"authorization_confirmed": True}


def start_without_protocol(mobile, tokens, session_type="adulto", **extra):
    return mobile.client.post("/mobile/sessions", headers=bearer(tokens),
                              json={"session_type": session_type, **CONFIRMED, **extra})


def test_summary_has_only_the_signed_in_account_data(env, mobile):  # noqa: F811
    emotional, _ = stimuli(env)
    mine = env.client.post("/protocols", headers=headers(env, env.user_1), json={
        "name": "Mío", "description": "", "for_children": True, "steps": [step(emotional)]}).json()
    env.client.post("/protocols", headers=headers(env, env.user_2), json={
        "name": "Ajeno", "description": "", "for_children": False, "steps": [step(emotional)]})
    accept_commitment(env, env.user_1)
    accept_commitment(env, env.user_2)
    tokens = signed_in(mobile, "usuario1@example.com")
    own = start_without_protocol(mobile, tokens).json()
    foreign = start_without_protocol(mobile, signed_in(mobile, "usuario2@example.com")).json()

    body = mobile.client.get("/mobile/summary", headers=bearer(tokens)).json()
    assert "participants" not in body
    assert [item["code"] for item in body["recent_sessions"]] == [own["code"]]
    assert [item["code"] for item in body["today_sessions"]] == [own["code"]]
    assert body["recent_sessions"][0]["audience"] == "adulto"
    assert [(item["id"], item["audience"]) for item in body["protocols"]] == [(mine["id"], "infantil")]
    assert "tutor autorizó por escrito" in body["protocols"][0]["confirmation"]
    assert {item["value"] for item in body["audiences"]} == {"propia", "adulto", "infantil"}
    assert foreign["code"] not in str(body) and foreign["session_id"] not in str(body)

    # El docente del grupo tampoco ve en el aplicativo las sesiones de su usuario.
    docente = mobile.client.get("/mobile/summary", headers=bearer(signed_in(mobile, "docente.a@example.com"))).json()
    assert docente["recent_sessions"] == [] and docente["today_sessions"] == []
    assert ("view", "mobile_summary", "success") in audit_actions(env)


# --- Sesión desde el móvil --------------------------------------------------------------

def ready_session(env, mobile, for_children=False):  # noqa: F811
    emotional, _ = stimuli(env)
    questionnaire = create_questionnaire(env, env.user_1)
    accept_commitment(env, env.user_1)
    env.commitments.accept(env.user_1, load_text("child_notice").version, "child_notice")
    body = {"name": "Secuencia móvil", "description": "", "for_children": for_children,
            "steps": [step(emotional, exposure=6, capture=2)], "pre_questionnaire_id": questionnaire["id"],
            "post_questionnaire_id": None}
    protocol = env.client.post("/protocols", headers=headers(env, env.user_1), json=body).json()
    tokens = signed_in(mobile, "usuario1@example.com")
    return protocol, emotional, tokens


def start(mobile, tokens, protocol, confirmed=True):
    return mobile.client.post("/mobile/sessions", headers=bearer(tokens),
                              json={"protocol_id": protocol["id"], "authorization_confirmed": confirmed})


def started_id(mobile, tokens, protocol):
    response = start(mobile, tokens, protocol)
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


def send_frame(mobile, tokens, session_id):
    return mobile.client.post(f"/mobile/sessions/{session_id}/frames", content=FRAME,
                              headers={**bearer(tokens), "Content-Type": "image/jpeg"})


def calibrate(env, mobile, tokens, session_id):  # noqa: F811
    assert mobile.client.post(f"/mobile/sessions/{session_id}/calibration", headers=bearer(tokens)).status_code == 200
    for _ in range(6):
        assert send_frame(mobile, tokens, session_id).status_code == 200
        env.clock.now += timedelta(seconds=0.6)


def test_full_session_with_a_protocol_from_the_device(env, mobile):  # noqa: F811
    protocol, emotional, tokens = ready_session(env, mobile)
    options = mobile.client.get("/mobile/protocols", headers=bearer(tokens))
    assert [item["id"] for item in options.json()] == [protocol["id"]]
    assert options.json()[0]["audience"] == "adulto"

    # Sin la confirmación no hay sesión.
    refused = start(mobile, tokens, protocol, confirmed=False)
    assert refused.status_code == 422 and "persona adulta" in refused.json()["detail"]["message"]
    started = start(mobile, tokens, protocol)
    assert started.status_code == 201, started.text
    session_id = started.json()["session_id"]
    assert started.json()["code"].startswith("S-") and started.json()["audience"] == "adulto"
    assert "view_token" not in started.text and "participant" not in started.text
    # No hay un segundo paso de confirmación: empieza en el cuestionario previo.
    assert mobile.client.post(f"/mobile/sessions/{session_id}/confirm", headers=bearer(tokens),
                              json={}).status_code in (404, 405)
    current = mobile.client.get(f"/mobile/sessions/{session_id}/next", headers=bearer(tokens)).json()
    assert current["phase"] == "pre_questionnaire" and current["questionnaire"]["moment"] == "pre"
    assert current["code"] == started.json()["code"]
    assert {item["id"] for item in current["questionnaire"]["questions"]} >= {"animo", "energia"}

    answered = mobile.client.post(f"/mobile/sessions/{session_id}/questionnaires/pre", headers=bearer(tokens),
                                  json={"answers": {"animo": 3, "energia": 4}})
    assert answered.status_code == 201 and answered.json()["phase"] == "calibration"
    calibrate(env, mobile, tokens, session_id)

    current = mobile.client.get(f"/mobile/sessions/{session_id}/next", headers=bearer(tokens)).json()
    assert current["phase"] == "stimuli" and current["send_frames"] is True
    assert current["stimulus"]["title"] == emotional["title"]
    for word in RESULT_WORDS:
        assert word not in str(current).lower()

    image = mobile.client.get(current["stimulus"]["image_url"])
    assert image.status_code == 200 and image.headers["content-type"].startswith("image/")

    env.clock.now += timedelta(seconds=2)
    assert send_frame(mobile, tokens, session_id).json() == {"phase": "stimuli", "capture_status": []}
    captures = env.guided.repository.list_captures(session_id)
    assert len(captures) == 1 and captures[0].quality.value == "good"

    stopped = mobile.client.post(f"/mobile/sessions/{session_id}/stop", headers=bearer(tokens),
                                 json={"reason": "participant"})
    assert stopped.json() == {"phase": "stopped"}
    # Con la sesión terminada, la imagen ya no se sirve aunque la URL no haya vencido.
    assert mobile.client.get(current["stimulus"]["image_url"]).status_code == 403
    actions = audit_actions(env)
    assert ("view", "stimulus_image", "success") in actions and ("view", "stimulus_image", "denied") in actions
    assert ("view", "guided_session", "success") in actions


def test_the_mobile_api_works_without_a_protocol(env, mobile):  # noqa: F811
    accept_commitment(env, env.user_1)
    tokens = signed_in(mobile, "usuario1@example.com")
    # Sin protocolo hay que decir con quién es la sesión y confirmar.
    missing = mobile.client.post("/mobile/sessions", headers=bearer(tokens), json=CONFIRMED)
    assert missing.status_code == 422
    assert start_without_protocol(mobile, tokens, "propia", authorization_confirmed=False).status_code == 422
    # participant_id ya no existe en el contrato.
    legacy = mobile.client.post("/mobile/sessions", headers=bearer(tokens),
                                json={"participant_id": "p-1", "protocol_id": "x"})
    assert legacy.status_code == 422
    started = start_without_protocol(mobile, tokens, "propia")
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["phase"] == "calibration" and body["has_protocol"] is False and body["audience"] == "propia"
    session_id = body["session_id"]
    calibrate(env, mobile, tokens, session_id)
    current = mobile.client.get(f"/mobile/sessions/{session_id}/next", headers=bearer(tokens)).json()
    assert current["phase"] == "live" and current["send_frames"] is True
    assert current["stimulus"] is None and current["questionnaire"] is None
    for _ in range(3):
        env.clock.now += timedelta(seconds=3)
        assert send_frame(mobile, tokens, session_id).status_code == 200
    assert env.guided.repository.list_captures(session_id)
    finished = mobile.client.post(f"/mobile/sessions/{session_id}/finish", headers=bearer(tokens))
    assert finished.json() == {"phase": "finished", "code": body["code"]}
    assert env.sessions.get_session(session_id).state.value == "completed"
    # Solo se termina así una sesión sin protocolo.
    assert mobile.client.post(f"/mobile/sessions/{session_id}/finish", headers=bearer(tokens)).status_code == 409


def test_a_child_session_asks_for_the_tutor_and_the_notice_the_first_time(env, mobile):  # noqa: F811
    accept_commitment(env, env.user_1)
    tokens = signed_in(mobile, "usuario1@example.com")
    unconfirmed = start_without_protocol(mobile, tokens, "infantil", authorization_confirmed=False)
    assert unconfirmed.status_code == 422 and "tutor autorizó" in unconfirmed.json()["detail"]["message"]
    notice = start_without_protocol(mobile, tokens, "infantil")
    assert notice.status_code == 428 and error_code(notice) == "child_notice_required"
    version = load_text("child_notice").version
    started = start_without_protocol(mobile, tokens, "infantil", child_notice_version=version)
    assert started.status_code == 201 and started.json()["audience"] == "infantil"
    assert start_without_protocol(mobile, tokens, "infantil").status_code == 201


def test_a_childrens_protocol_asks_for_the_tutor_confirmation(env, mobile):  # noqa: F811
    protocol, _, tokens = ready_session(env, mobile, for_children=True)
    refused = start(mobile, tokens, protocol, confirmed=False)
    assert refused.status_code == 422 and "tutor autorizó" in refused.json()["detail"]["message"]
    started = start(mobile, tokens, protocol)
    assert started.status_code == 201 and started.json()["audience"] == "infantil"


def test_another_account_cannot_drive_or_start_the_session(env, mobile):  # noqa: F811
    protocol, _, tokens = ready_session(env, mobile)
    session_id = started_id(mobile, tokens, protocol)
    other = signed_in(mobile, "usuario2@example.com")
    accept_commitment(env, env.user_2)
    assert mobile.client.get(f"/mobile/sessions/{session_id}/next", headers=bearer(other)).status_code == 403
    assert send_frame(mobile, other, session_id).status_code == 403
    assert mobile.client.post(f"/mobile/sessions/{session_id}/finish", headers=bearer(other)).status_code == 403
    foreign = start(mobile, other, protocol)
    assert foreign.status_code == 404 and error_code(foreign) == "not_found"


def test_an_expired_or_altered_stimulus_url_is_rejected(env, mobile):  # noqa: F811
    protocol, emotional, tokens = ready_session(env, mobile)
    session_id = started_id(mobile, tokens, protocol)
    expires, signature = mobile.signer.sign(env.user_1.id, session_id, emotional["id"])
    url = f"/mobile/stimulus-images/{session_id}/{emotional['id']}?expires={expires}&signature={signature}"
    assert mobile.client.get(url).status_code == 200
    assert mobile.client.get(url.replace(signature, "0" * 64)).status_code == 403
    assert mobile.client.get(url.replace(f"expires={expires}", f"expires={expires + 60}")).status_code == 403
    mobile.signer_clock.now += timedelta(seconds=121)
    expired = mobile.client.get(url)
    assert expired.status_code == 403 and error_code(expired) == "invalid_or_expired_url"


def test_the_mobile_capture_never_stores_the_image(env, mobile):  # noqa: F811
    protocol, _, tokens = ready_session(env, mobile)
    session_id = started_id(mobile, tokens, protocol)
    mobile.client.post(f"/mobile/sessions/{session_id}/questionnaires/pre", headers=bearer(tokens),
                       json={"answers": {"animo": 3, "energia": 4}})
    mobile.client.post(f"/mobile/sessions/{session_id}/calibration", headers=bearer(tokens))
    for _ in range(12):
        assert send_frame(mobile, tokens, session_id).status_code == 200
        env.clock.now += timedelta(seconds=0.6)
    assert env.frames_assessed >= 6 and env.guided.repository.list_captures(session_id)

    marker = b"MARCA-DEL-CUADRO-MOVIL"
    with env.engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            for row in connection.execute(select(table)):
                for value in row:
                    raw = value if isinstance(value, bytes) else str(value).encode("utf-8", "ignore")
                    assert marker not in raw, f"{table.name} guardó el cuadro"
    assert "frame" not in {column["name"] for column in inspect(env.engine).get_columns("expression_captures")}


def test_a_frame_must_be_jpeg(env, mobile):  # noqa: F811
    protocol, _, tokens = ready_session(env, mobile)
    session_id = started_id(mobile, tokens, protocol)
    wrong = mobile.client.post(f"/mobile/sessions/{session_id}/frames", content=FRAME,
                               headers={**bearer(tokens), "Content-Type": "image/png"})
    assert wrong.status_code == 415


def test_a_flagged_capture_reports_only_the_quality_issue(env, mobile):  # noqa: F811
    protocol, _, tokens = ready_session(env, mobile)
    session_id = started_id(mobile, tokens, protocol)
    mobile.client.post(f"/mobile/sessions/{session_id}/questionnaires/pre", headers=bearer(tokens),
                       json={"answers": {"animo": 3, "energia": 4}})
    calibrate(env, mobile, tokens, session_id)
    env.clock.now += timedelta(seconds=2)
    env.frame_result = FrameAssessment((QualityIssue.NO_FACE,))
    body = send_frame(mobile, tokens, session_id).json()
    assert body == {"phase": "stimuli", "capture_status": ["no_face"]}


# --- HTTPS y cabeceras ---------------------------------------------------------------------

def test_production_rejects_plain_http_and_accepts_https(env):  # noqa: F811
    plain = build(env, production=True)
    with plain.client:
        response = plain.client.get("/mobile/status")
        assert response.status_code == 403 and error_code(response) == "https_required"
        assert login(plain, "usuario1@example.com").status_code == 403
    secure = build(env, production=True, base_url="https://testserver")
    with secure.client:
        assert secure.client.get("/mobile/status").status_code == 200


def test_mobile_responses_are_not_cached(mobile):
    assert mobile.client.get("/mobile/status").headers["cache-control"] == "no-store"
    tokens = signed_in(mobile, "usuario1@example.com")
    response = mobile.client.get("/mobile/summary", headers=bearer(tokens))
    assert response.headers["cache-control"] == "no-store"
