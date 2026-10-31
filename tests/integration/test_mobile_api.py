"""API del aplicativo móvil: inicio de sesión y tokens revocables; consulta de
sesiones, reportes y estadísticas con los mismos permisos que la web, y
revisión del reporte desde el teléfono. El aplicativo no conduce sesiones:
ninguna ruta móvil recibe capturas (SQLite en memoria, analizador falso)."""
from __future__ import annotations

from dataclasses import replace
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from emotv.application.login_throttle import LoginThrottle
from emotv.application.mobile_auth_service import MobileAuthService
from emotv.config import LoginLimits
from emotv.infrastructure.persistence import PostgresLoginAttemptRepository, PostgresMobileSessionRepository
from emotv.interfaces.web.mobile_router import create_mobile_router
from emotv.interfaces.web.security import configure_web_security, load_web_settings
from emotv.interfaces.web.session_router import create_visible_sessions
from tests.integration.test_privacy_accounts import KEY, accept_commitment, audit_actions, env, headers  # noqa: F401
from tests.integration.test_session_insights import run_session, setup

PASSWORDS = {"usuario1@example.com": "usuario-1-pass-123", "usuario2@example.com": "usuario-2-pass-123",
             "docente.a@example.com": "docente-a-pass-123", "docente.b@example.com": "docente-b-pass-123",
             "facultad@example.com": "admin-password-123", "soporte@example.com": "superadmin-pass-123"}
TEXT = "La persona observó las imágenes con atención y pidió una pausa breve."


def build(env, *, production: bool = False, base_url: str = "http://testserver"):  # noqa: F811
    throttle = LoginThrottle(PostgresLoginAttemptRepository(env.factory), LoginLimits(3, 50, 15))
    service = MobileAuthService(PostgresMobileSessionRepository(env.factory), env.auth, env.users, env.audit,
                                throttle, clock=env.clock)
    app = FastAPI()
    configure_web_security(app, load_web_settings({"ENVIRONMENT": "test"}))
    app.include_router(create_mobile_router(
        service, env.users, audit=env.audit,
        visible_sessions=create_visible_sessions(env.sessions, env.students, env.assignments, env.authorization),
        insights=env.insights, reports=env.reports, statistics=env.statistics,
        production=production, api_version="1.0.0rc1", min_app_version="1.2.0", clock=env.clock))
    return SimpleNamespace(client=TestClient(app, base_url=base_url), service=service)


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
    assert body["services"] == {"login": True, "sessions": True, "reports": True, "statistics": True}


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


# --- Sesiones: solo consulta -------------------------------------------------------------

def finished_session(env):  # noqa: F811
    """Sesión conducida en la web por el usuario 1 (grupo del docente A)."""
    return run_session(env, setup(env))


def get(mobile, path, email, **params):
    return mobile.client.get(path, headers=bearer(signed_in(mobile, email)), params=params)


def test_the_mobile_api_does_not_conduct_sessions(mobile):
    """Ninguna captura sale del teléfono: no existen rutas para iniciar ni conducir sesiones."""
    # El esquema lista también las rutas de los routers incluidos.
    paths = mobile.client.app.openapi()["paths"]
    assert "/mobile/sessions" in paths
    assert not [path for path in paths
                if any(word in path for word in ("frame", "calibration", "stimulus-images", "protocols", "advance"))]
    assert "post" not in paths["/mobile/sessions"]
    tokens = signed_in(mobile, "usuario1@example.com")
    response = mobile.client.post("/mobile/sessions", headers=bearer(tokens), json={"session_type": "adulto"})
    assert response.status_code == 405


def test_summary_and_list_show_what_the_account_already_sees_on_the_web(env, mobile):  # noqa: F811
    session_id = finished_session(env)
    code = env.sessions.get_session(session_id).code

    own = get(mobile, "/mobile/summary", "usuario1@example.com").json()
    assert [item["code"] for item in own["recent_sessions"]] == [code]
    assert own["recent_sessions"][0]["mine"] is True and own["recent_sessions"][0]["report_status"] is None
    assert own["pending_reviews"] == 0 and "protocols" not in own and "audiences" not in own

    # El docente del grupo ve la sesión de su usuario, marcada como ajena.
    group = get(mobile, "/mobile/sessions", "docente.a@example.com").json()
    assert [(item["code"], item["mine"]) for item in group] == [(code, False)]
    for email in ("usuario2@example.com", "docente.b@example.com"):
        assert get(mobile, "/mobile/sessions", email).json() == []
        assert code not in str(get(mobile, "/mobile/summary", email).json())
    assert ("view", "mobile_sessions", "success") in audit_actions(env)


def test_session_detail_has_the_timeline_and_metrics_only_for_who_can_access(env, mobile):  # noqa: F811
    session_id = finished_session(env)
    detail = get(mobile, f"/mobile/sessions/{session_id}", "usuario1@example.com")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["session"]["id"] == session_id
    assert set(body["timeline"]["lanes"]) >= {"stimuli", "captures", "questionnaires"}
    assert body["metrics"]["totals"]["emotional_stimuli"] == 2
    assert get(mobile, f"/mobile/sessions/{session_id}", "docente.a@example.com").status_code == 200
    for email in ("usuario2@example.com", "docente.b@example.com"):
        denied = get(mobile, f"/mobile/sessions/{session_id}", email)
        assert denied.status_code == 403 and error_code(denied) == "forbidden"
    missing = get(mobile, "/mobile/sessions/no-existe", "usuario1@example.com")
    assert missing.status_code == 404 and error_code(missing) == "not_found"


# --- Reporte desde el teléfono ------------------------------------------------------------

def test_the_report_goes_through_the_docente_review_from_the_phone(env, mobile):  # noqa: F811
    session_id = finished_session(env)
    user = bearer(signed_in(mobile, "usuario1@example.com"))
    docente = bearer(signed_in(mobile, "docente.a@example.com"))
    created = mobile.client.post(f"/mobile/sessions/{session_id}/report", headers=user)
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]
    assert created.json()["status"] == "draft" and created.json()["can_edit"] is True

    empty = mobile.client.post(f"/mobile/reports/{report_id}/submit", headers=user)
    assert empty.status_code == 422 and error_code(empty) == "invalid"
    mobile.client.put(f"/mobile/reports/{report_id}", headers=user, json={"narrative": TEXT})
    sent = mobile.client.post(f"/mobile/reports/{report_id}/submit", headers=user).json()
    assert sent["status"] == "submitted" and sent["can_edit"] is False

    # Pendiente del docente asignado; el otro docente no lo ve ni lo revisa.
    pending = mobile.client.get("/mobile/reviews", headers=docente).json()
    assert [(item["id"], item["report_id"]) for item in pending] == [(session_id, report_id)]
    assert get(mobile, "/mobile/summary", "docente.a@example.com").json()["pending_reviews"] == 1
    assert get(mobile, "/mobile/reviews", "docente.b@example.com").json() == []
    other = mobile.client.post(f"/mobile/reports/{report_id}/comments", json={"text": "Revisa"},
                               headers=bearer(signed_in(mobile, "docente.b@example.com")))
    assert other.status_code == 403
    # El usuario no se aprueba a sí mismo.
    assert mobile.client.post(f"/mobile/reports/{report_id}/approve", headers=user).status_code == 403

    commented = mobile.client.post(f"/mobile/reports/{report_id}/comments", headers=docente,
                                   json={"section": "narrative", "text": "Describe la pausa con más detalle."})
    assert [item["text"] for item in commented.json()["comments"]] == ["Describe la pausa con más detalle."]
    returned = mobile.client.post(f"/mobile/reports/{report_id}/return", headers=docente).json()
    assert returned["status"] == "changes_requested"
    assert mobile.client.get("/mobile/reviews", headers=docente).json() == []

    # El usuario responde corrigiendo el texto y vuelve a enviarlo.
    seen = mobile.client.get(f"/mobile/sessions/{session_id}/report", headers=user).json()
    assert seen["comments"][0]["section"] == "narrative" and seen["can_edit"] is True
    mobile.client.put(f"/mobile/reports/{report_id}", headers=user, json={"narrative": TEXT + " Duró un minuto."})
    mobile.client.post(f"/mobile/reports/{report_id}/submit", headers=user)
    approved = mobile.client.post(f"/mobile/reports/{report_id}/approve", headers=docente).json()
    assert approved["status"] == "approved" and approved["can_review"] is False
    again = mobile.client.post(f"/mobile/reports/{report_id}/approve", headers=docente)
    assert again.status_code == 409 and error_code(again) == "conflict"
    listed = get(mobile, "/mobile/sessions", "usuario1@example.com").json()
    assert listed[0]["report_status"] == "approved"


def test_reviews_are_only_for_the_docente(mobile):
    response = get(mobile, "/mobile/reviews", "usuario1@example.com")
    assert response.status_code == 403 and error_code(response) == "forbidden"


# --- Estadísticas agregadas ---------------------------------------------------------------

def test_statistics_count_sessions_and_never_list_people(env, mobile):  # noqa: F811
    finished_session(env)
    mine = get(mobile, "/mobile/statistics", "usuario1@example.com").json()
    assert mine["scope"] == "mine" and mine["sessions"]["total"] == 1
    group = get(mobile, "/mobile/statistics", "docente.a@example.com", scope="group").json()
    assert group["sessions"]["total"] == 1
    assert "by_user" not in group and "usuario1@example.com" not in str(group)
    assert get(mobile, "/mobile/statistics", "usuario1@example.com", scope="group").status_code == 403
    dates = get(mobile, "/mobile/statistics", "usuario1@example.com", date_from="2026-10-02", date_to="2026-10-01")
    assert dates.status_code == 422


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
