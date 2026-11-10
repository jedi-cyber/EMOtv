"""Pantalla de la persona en Android (bloque 8): quien conduce pide en la web un
código de un solo uso y el aplicativo lo canjea por el enlace de esa pantalla.
El enlace solo abre la sesión en curso, vence al terminar, se invalida con otro
enlace o código, sirve para reconectarse y no admite respuestas duplicadas.
Android no envía imágenes: solo se vinculan sesiones sin cámara.
(SQLite en memoria, reloj falso y analizador falso; sin modelos.)"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect

from emotv.application.login_throttle import LoginThrottle
from emotv.application.mobile_auth_service import MobileAuthService
from emotv.config import LoginLimits
from emotv.domain.guided_session import PAIRING_ALPHABET, PAIRING_LENGTH, PAIRING_SECONDS, GameOutcome, GuidedRun
from emotv.infrastructure.persistence import PostgresLoginAttemptRepository, PostgresMobileSessionRepository
from emotv.interfaces.web.mobile_router import create_mobile_router
from emotv.interfaces.web.security import configure_web_security, load_web_settings
from emotv.interfaces.web.session_router import create_visible_sessions
from tests.integration.test_guided_sessions import begin_steps, guided, post, protocol, state, stimuli, view, wait
from tests.integration.test_mobile_api import bearer, signed_in
from tests.integration.test_practice_persistence import engine  # noqa: F401
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_similar_game import bank, correct_key, round_info, save, similar, wrong_keys

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261107_43_android_screen.py"
DRAWING = {"kind": "drawing", "exposure_seconds": 30}


@pytest.fixture
def mobile(env):  # noqa: F811
    throttle = LoginThrottle(PostgresLoginAttemptRepository(env.factory), LoginLimits(3, 50, 15))
    service = MobileAuthService(PostgresMobileSessionRepository(env.factory), env.auth, env.users, env.audit,
                                throttle, clock=env.clock)
    app = FastAPI()
    configure_web_security(app, load_web_settings({"ENVIRONMENT": "test"}))
    app.include_router(create_mobile_router(
        service, env.users, audit=env.audit,
        visible_sessions=create_visible_sessions(env.sessions, env.students, env.assignments, env.authorization),
        insights=env.insights, reports=env.reports, statistics=env.statistics,
        participation=env.guided.claim_android_code, api_version="1.0.0rc1", min_app_version="1.2.0",
        clock=env.clock))
    built = SimpleNamespace(client=TestClient(app))
    with built.client:
        yield built


def start(env, steps=(DRAWING, DRAWING)):  # noqa: F811
    session_id, token = guided(env, protocol(env, list(steps)))
    begin_steps(env, session_id, token)
    return session_id, token


def code(env, session_id, user=None):  # noqa: F811
    return post(env, session_id, "android-code", user=user)


def claim(mobile, value):
    return mobile.client.post("/mobile/participation", json={"code": value})


def paired(env, mobile, session_id):  # noqa: F811
    response = claim(mobile, code(env, session_id).json()["code"])
    assert response.status_code == 200, response.text
    return response.json()["participant_token"]


def answer(env, token, expression):  # noqa: F811
    return env.client.post(f"/participant-view/{token}/answer", json={"expression": expression})


# --- Dominio ---------------------------------------------------------------------------------


def test_el_codigo_y_la_pantalla_se_validan():
    assert PAIRING_LENGTH == 8 and not set("0O1IL") & set(PAIRING_ALPHABET) and PAIRING_SECONDS == 300
    with pytest.raises(ValueError):
        GuidedRun("s", "u", created_at=None, view_device="ios")
    with pytest.raises(ValueError):
        GuidedRun("s", "u", created_at=None, pairing_hash="x")


# --- Vincular ----------------------------------------------------------------------------------


def test_quien_conduce_pide_un_codigo_y_android_muestra_la_actividad(env, mobile):  # noqa: F811
    session_id, web_token = start(env)
    response = code(env, session_id)
    assert response.status_code == 200
    body = response.json()
    assert len(body["code"]) == PAIRING_LENGTH and set(body["code"]) <= set(PAIRING_ALPHABET)
    assert body["expires_in"] == PAIRING_SECONDS
    screen = state(env, session_id)["screen"]
    assert screen["device"] == "web" and screen["pairing_expires_at"] is not None and screen["can_pair_android"]
    # Se acepta escrito en minúsculas, con espacios o con guion.
    claimed = claim(mobile, f" {body['code'][:4].lower()}-{body['code'][4:]} ")
    assert claimed.status_code == 200, claimed.text
    token = claimed.json()["participant_token"]
    assert claimed.json()["state_path"] == f"/participant-view/{token}"
    shown = view(env, token).json()
    assert shown["activity"] == {"kind": "drawing", "name": "Dibuja una cara", "number": 1, "total": 2}
    assert shown["capture_frames"] is False and shown["drawing"]["finished"] is False
    # La pantalla web anterior deja de valer y quien conduce ve que está en Android.
    assert view(env, web_token).status_code == 404
    screen = state(env, session_id)["screen"]
    assert screen == {"device": "android", "pairing_expires_at": None, "can_pair_android": True}
    # Nada del código en claro queda en la base.
    run = env.guided.repository.get_run(session_id)
    assert run.view_device == "android" and run.pairing_hash is None


def test_solo_quien_conduce_pide_el_codigo(env):  # noqa: F811
    session_id, _ = start(env)
    for user in (env.user_2, env.docente_a, env.docente_b, env.admin, env.superadmin):
        assert code(env, session_id, user=user).status_code in (403, 404)


def test_las_sesiones_con_camara_o_terminadas_no_se_vinculan(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, _ = start(env, [{"stimulus_id": emotional["id"], "exposure_seconds": 5, "capture_after_seconds": 0},
                                DRAWING])
    response = code(env, session_id)
    assert response.status_code == 409 and "cámara" in response.json()["detail"]
    assert state(env, session_id)["screen"]["can_pair_android"] is False
    # Al seguir sin cámara sí se puede.
    assert post(env, session_id, "continue-without-camera").status_code == 200
    assert code(env, session_id).status_code == 200
    drawing_id, _ = start(env)
    assert post(env, drawing_id, "stop", {"reason": "conductor"}).status_code == 200
    assert code(env, drawing_id).status_code == 409


# --- Caducidad e invalidación -------------------------------------------------------------------


def test_el_codigo_sirve_una_vez_y_vence(env, mobile):  # noqa: F811
    session_id, _ = start(env)
    first = code(env, session_id).json()["code"]
    assert claim(mobile, first).status_code == 200
    again = claim(mobile, first)
    assert again.status_code == 404 and again.json()["detail"]["code"] == "invalid_code"
    late = code(env, session_id).json()["code"]
    wait(env, PAIRING_SECONDS + 1)
    assert claim(mobile, late).status_code == 404
    assert state(env, session_id)["screen"]["pairing_expires_at"] is None


def test_un_codigo_nuevo_reemplaza_al_anterior_sin_canjear(env, mobile):  # noqa: F811
    session_id, _ = start(env)
    old = code(env, session_id).json()["code"]
    new = code(env, session_id).json()["code"]
    assert claim(mobile, old).status_code == 404 and claim(mobile, new).status_code == 200


def test_un_enlace_o_codigo_nuevo_invalida_la_pantalla_anterior(env, mobile):  # noqa: F811
    session_id, _ = start(env)
    first = paired(env, mobile, session_id)
    second = paired(env, mobile, session_id)                         # otra tableta
    assert view(env, first).status_code == 404 and view(env, second).status_code == 200
    web = post(env, session_id, "view-link").json()["view_token"]
    assert view(env, second).status_code == 404 and view(env, web).status_code == 200
    assert state(env, session_id)["screen"]["device"] == "web"


def test_los_codigos_equivocados_se_limitan(env, mobile):  # noqa: F811
    for _ in range(3):
        assert claim(mobile, "ABCDEFGH").status_code == 404
    session_id, _ = start(env)
    blocked = claim(mobile, code(env, session_id).json()["code"])
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers


# --- Acceso limitado --------------------------------------------------------------------------


def test_el_enlace_solo_abre_la_pantalla_de_la_sesion(env, mobile):  # noqa: F811
    session_id, _ = start(env)
    token = paired(env, mobile, session_id)
    as_bearer = {"Authorization": f"Bearer {token}"}
    for path in ("/mobile/sessions", f"/mobile/sessions/{session_id}", "/mobile/statistics"):
        assert mobile.client.get(path, headers=as_bearer).status_code == 401
    for path in (f"/sessions/{session_id}/metrics", f"/guided-sessions/{session_id}", f"/sessions/{session_id}/timeline"):
        assert env.client.get(path, headers=as_bearer).status_code == 401
    assert env.client.post(f"/guided-sessions/{session_id}/skip", headers=as_bearer).status_code == 401
    # La pantalla no recibe datos de quien conduce ni de la sesión.
    shown = view(env, token).json()
    assert not {"session_id", "session_code", "steps", "screen", "steps_log"} & set(shown)
    # Android no envía imágenes.
    frame = env.client.post(f"/participant-view/{token}/frames", content=b"\xff\xd8\xff",
                            headers={"Content-Type": "image/jpeg"})
    assert frame.status_code == 409 and env.frames_assessed == 0


def test_la_consulta_y_la_revision_docente_siguen_igual(env, mobile):  # noqa: F811
    session_id, _ = start(env)
    paired(env, mobile, session_id)
    tokens = signed_in(mobile, "docente.a@example.com")
    assert mobile.client.get("/mobile/sessions", headers=bearer(tokens)).status_code == 200
    assert mobile.client.get(f"/mobile/sessions/{session_id}", headers=bearer(tokens)).status_code == 200
    other = signed_in(mobile, "docente.b@example.com")
    assert mobile.client.get(f"/mobile/sessions/{session_id}", headers=bearer(other)).status_code in (403, 404)


# --- Reconexión, duplicados y cierre ---------------------------------------------------------------


def test_al_reconectarse_sigue_en_su_paso_y_no_duplica_respuestas(env, mobile):  # noqa: F811
    session_id, _ = start(env)
    token = paired(env, mobile, session_id)
    wait(env, 3)
    before = view(env, token).json()
    wait(env, 4)                                                       # se cortó la red unos segundos
    after = view(env, token).json()
    assert after["activity"] == before["activity"] and after["remaining_seconds"] < before["remaining_seconds"]
    assert answer(env, token, "happiness").json() == {"received": True}
    # El aplicativo reintenta la misma respuesta al recuperar la red.
    assert answer(env, token, "happiness").status_code == 409
    assert answer(env, token, "sadness").status_code == 409
    [item] = env.guided.repository.list_drawing_attempts(session_id)
    assert item.chosen_expression == "happiness"
    wait(env, 2.1)
    assert view(env, token).json()["activity"]["number"] == 2


def test_al_terminar_el_enlace_se_cierra(env, mobile):  # noqa: F811
    session_id, _ = start(env, [DRAWING])
    token = paired(env, mobile, session_id)
    answer(env, token, "happiness")
    wait(env, 2.1)
    assert state(env, session_id)["phase"] == "finished"
    assert view(env, token).status_code == 404
    stopped_id, _ = start(env)
    token = paired(env, mobile, stopped_id)
    pending = code(env, stopped_id).json()["code"]
    assert env.client.post(f"/participant-view/{token}/stop").json() == {"stopped": True}
    assert view(env, token).status_code == 404 and answer(env, token, "happiness").status_code == 404
    assert claim(mobile, pending).status_code == 404


def test_busca_la_misma_emocion_desde_android_termina_y_registra_el_resultado(env, mobile):  # noqa: F811
    """Bloque 10B: Android juega «Busca la misma emoción» con las mismas rutas que la
    web. Un toque repetido tras un corte no se registra dos veces y, al terminar,
    el resultado queda como respondido por la persona."""
    bank(env)
    response = save(env, [similar(rounds=2, options=3), DRAWING])
    assert response.status_code == 201, response.text
    session_id, _ = guided(env, response.json())
    begin_steps(env, session_id, _)
    token = paired(env, mobile, session_id)
    block = view(env, token).json()
    assert block["activity"]["kind"] == "game" and block["game"]["game_type"] == "similar"
    # La modelo y cada cara se piden con el enlace de Android.
    assert env.client.get(f"/participant-view/{token}/stimulus").status_code == 200
    for item in block["game"]["options"]:
        assert env.client.get(f"/participant-view/{token}/game/option/{item['key']}").status_code == 200

    def act(action, key=None):
        return env.client.post(f"/participant-view/{token}/game",
                               json={"action": action, **({"expression": key} if key else {})})

    # Ronda 1: una cara de otra emoción, repetida tras un corte, y luego la pareja.
    miss = wrong_keys(round_info(env, session_id))[0]
    assert act("answer", miss).status_code == 200
    assert act("answer", miss).status_code == 422
    assert act("answer", correct_key(round_info(env, session_id))).status_code == 200
    assert act("next").status_code == 200
    assert act("next").status_code == 409                               # no salta dos rondas
    assert view(env, token).json()["game"]["number"] == 2
    # Ronda 2: a la primera, y «Terminar el juego».
    assert act("answer", correct_key(round_info(env, session_id))).status_code == 200
    assert act("next").status_code == 200
    assert view(env, token).json()["game"]["state"] == "finished"
    assert act("next").status_code == 409

    [item] = env.guided.repository.list_game_attempts(session_id)
    assert item.game_type == "similar" and item.outcome is GameOutcome.COMPLETED
    assert (item.rounds_total, item.rounds_done, item.matched, item.first_try, item.help_used,
            item.by_conductor) == (2, 2, 2, 1, 0, 0)
    [exercise] = env.client.get(f"/sessions/{session_id}/metrics",
                                headers=headers(env, env.user_1)).json()["game"]["exercises"]
    assert exercise["game_type"] == "similar" and exercise["sentence"].startswith("Jugó 2 de 2 rondas.")
    wait(env, 2.1)
    assert view(env, token).json()["activity"]["kind"] == "drawing"     # sigue el paso siguiente


# --- Migración ------------------------------------------------------------------------------------


def _migration():
    spec = importlib.util.spec_from_file_location("migration_20261107_43", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, name: str) -> None:  # noqa: F811
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), name)()


def test_la_migracion_43_sigue_al_segundo_juego():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261107_43", "20261107_42")


def test_la_migracion_43_vuelve_atras_y_otra_vez_adelante(engine):  # noqa: F811
    columns = lambda: {item["name"] for item in inspect(engine).get_columns("guided_runs")}  # noqa: E731
    assert {"pairing_hash", "pairing_expires_at", "view_device"} <= columns()
    _run(engine, "downgrade")
    assert not {"pairing_hash", "pairing_expires_at", "view_device"} & columns()
    _run(engine, "upgrade")
    assert {"pairing_hash", "pairing_expires_at", "view_device"} <= columns()
    checks = {item["name"] for item in inspect(engine).get_check_constraints("guided_runs")}
    assert {"ck_guided_runs_view_device", "ck_guided_runs_pairing"} <= checks
