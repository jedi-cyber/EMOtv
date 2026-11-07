"""Resultados educativos (bloque 7): el reporte, las métricas y las estadísticas
distinguen reconocimiento, dibujo, juegos, práctica facial y actividades omitidas
o interrumpidas. Se calculan de las tablas que ya existen (sin migración), se
leen igual en sesiones antiguas, respetan los permisos y nunca guardan el dibujo.
(SQLite en memoria, reloj falso y analizador falso; sin modelos ni imágenes de personas.)"""
from __future__ import annotations

from sqlalchemy import inspect

from emotv.application.session_metrics import EDUCATIONAL_NOTICE, educational_summary, not_completed_sentence
from emotv.infrastructure.persistence.models import DrawingResultRecord
from emotv.infrastructure.persistence.postgres_guided_repositories import PostgresGuidedSessionRepository
from tests.integration.test_guided_sessions import begin_steps, guided, post, protocol, state, stimuli, view, wait
from tests.integration.test_matching_game import bank, game
from tests.integration.test_mobile_api import get as mobile_get, mobile  # noqa: F401
from tests.integration.test_practice_sessions import HAPPY, send
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_session_statistics import session

KEYS = {"recognition", "drawing", "games", "practice", "not_completed", "notice"}


def get(env, path, user=None):  # noqa: F811
    return env.client.get(path, headers=headers(env, user or env.user_1))


def answer(env, token, expression):  # noqa: F811
    return env.client.post(f"/participant-view/{token}/answer", json={"expression": expression})


def act(env, token, action, expression=None):  # noqa: F811
    body = {"action": action, **({"expression": expression} if expression else {})}
    return env.client.post(f"/participant-view/{token}/game", json=body)


def step_index(env, session_id):  # noqa: F811
    return state(env, session_id)["step_index"]


def full_session(env):  # noqa: F811
    """Una sesión con cada tipo de actividad: práctica lograda, reconocimiento y
    dibujo respondidos, un juego completo repetido, un dibujo omitido, un juego
    interrumpido y un dibujo que no llegó a aplicarse."""
    emotional, _ = stimuli(env)
    bank(env)
    item = protocol(env, [
        {"kind": "practice", "target_expression": "happiness", "hold_seconds": 2, "exposure_seconds": 20},
        {"kind": "recognition", "stimulus_id": emotional["id"], "exposure_seconds": 10},
        {"kind": "drawing", "exposure_seconds": 30},
        game(rounds=2),
        {"kind": "drawing", "exposure_seconds": 30},
        game(rounds=2),
        {"kind": "drawing", "exposure_seconds": 30},
    ])
    session_id, token = guided(env, item)
    begin_steps(env, session_id, token)
    assert step_index(env, session_id) == 0
    send(env, token, HAPPY, count=6)
    assert state(env, session_id)["practice"]["achieved"] is True
    wait(env, 25)
    send(env, token, HAPPY, count=1)
    assert step_index(env, session_id) == 1

    assert answer(env, token, emotional["expected_expression"]).json() == {"received": True}
    wait(env, 2.1)
    view(env, token)
    assert step_index(env, session_id) == 2
    assert answer(env, token, "happiness").json() == {"received": True}
    wait(env, 2.1)
    view(env, token)
    assert step_index(env, session_id) == 3

    for attempt in range(2):                                           # el juego y su repetición
        for _ in range(2):
            act(env, token, "answer", state(env, session_id)["game"]["target_expression"])
            act(env, token, "next")
        if attempt == 0:
            assert post(env, session_id, "repeat").status_code == 200
    wait(env, 2.1)
    view(env, token)
    assert step_index(env, session_id) == 4

    assert post(env, session_id, "skip").status_code == 200
    assert step_index(env, session_id) == 5
    assert env.client.post(f"/participant-view/{token}/stop").json() == {"stopped": True}
    assert state(env, session_id)["phase"] == "stopped"
    return session_id


# --- Resumen ---------------------------------------------------------------------------------


def test_sin_actividades_no_hay_resumen_educativo():
    assert educational_summary({"recognition": None, "drawing": None, "game": None, "practice": None}) is None
    assert not_completed_sentence(0, 0, 0) == "Todas las actividades llegaron a su final."
    assert not_completed_sentence(1, 2, 1) == ("1 actividad se omitió, 2 quedaron interrumpidas "
                                               "y 1 no llegó a aplicarse.")


def test_la_sesion_distingue_cada_actividad_y_las_que_no_terminaron(env):  # noqa: F811
    session_id = full_session(env)
    block = get(env, f"/sessions/{session_id}/metrics").json()["educational"]
    assert set(block) == KEYS and block["notice"] == EDUCATIONAL_NOTICE
    assert {key: block["practice"][key] for key in ("exercises", "applied", "achieved")} == {
        "exercises": 1, "applied": 1, "achieved": 1}
    assert {key: block["recognition"][key] for key in ("exercises", "applied", "matched")} == {
        "exercises": 1, "applied": 1, "matched": 1}
    drawing = block["drawing"]
    assert (drawing["exercises"], drawing["completed"]) == (3, 1)
    assert drawing["indicated"] == [{"expression": "happiness", "count": 1}]
    assert drawing["sentence"] == "Completó 1 de 3 dibujos señalando una emoción: alegría (1)."
    games = block["games"]
    assert (games["games"], games["played"], games["attempts"]) == (2, 2, 3)
    assert (games["rounds_total"], games["rounds_done"], games["matched"]) == (4, 2, 2)
    assert games["sentence"].endswith("Se repitió 1 vez (cuenta el primer intento).")
    pending = block["not_completed"]
    assert [(item["step_index"], item["activity"], item["status"]) for item in pending["items"]] == [
        (4, "Dibujo", "skipped"), (5, "Juego de emparejar", "stopped"), (6, "Dibujo", "not_reached")]
    assert (pending["skipped"], pending["stopped"], pending["not_reached"]) == (1, 1, 1)
    assert pending["sentence"] == "1 actividad se omitió, 1 quedó interrumpida y 1 no llegó a aplicarse."
    # Describe; no valora, no puntúa y no diagnostica.
    text = str({key: value for key, value in block.items() if key != "notice"}).lower()
    for word in ("puntaje", "score", "diagn", "trastorno", "bien", "mal "):
        assert word not in text


def test_el_reporte_muestra_el_mismo_resumen_que_las_metricas(env):  # noqa: F811
    session_id = full_session(env)
    report = env.client.post(f"/sessions/{session_id}/report", headers=headers(env, env.user_1))
    assert report.status_code == 201, report.text
    metrics = get(env, f"/sessions/{session_id}/metrics").json()["educational"]
    assert report.json()["metrics"]["educational"] == metrics
    again = get(env, f"/reports/{report.json()['id']}", env.docente_a)
    assert again.status_code == 200 and again.json()["metrics"]["educational"] == metrics


def test_solo_quien_condujo_y_su_docente_ven_los_resultados(env):  # noqa: F811
    session_id = full_session(env)
    assert get(env, f"/sessions/{session_id}/metrics", env.docente_a).json()["educational"] is not None
    for user in (env.docente_b, env.user_2, env.admin, env.superadmin):
        assert get(env, f"/sessions/{session_id}/metrics", user).status_code in (403, 404)


def test_las_sesiones_antiguas_se_leen_sin_resumen(env):  # noqa: F811
    old = session(env, env.user_1)                                     # sesión guardada antes, sin protocolo
    metrics = get(env, f"/sessions/{old.id}/metrics")
    assert metrics.status_code == 200 and metrics.json()["educational"] is None
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [{"stimulus_id": emotional["id"], "exposure_seconds": 5,
                                                    "capture_after_seconds": 0}]))
    assert get(env, f"/sessions/{session_id}/metrics").json()["educational"] is None


def test_el_dibujo_no_se_guarda(env):  # noqa: F811
    columns = {column.name for column in inspect(DrawingResultRecord).columns}
    assert not columns & {"image", "drawing", "strokes", "data", "content", "picture"}
    item = protocol(env, [{"kind": "drawing", "exposure_seconds": 30}])
    session_id, token = guided(env, item)
    begin_steps(env, session_id, token)
    extra = env.client.post(f"/participant-view/{token}/answer",
                            json={"expression": "happiness", "drawing": "data:image/png;base64,AAAA"})
    assert extra.status_code == 422
    assert not list(env.guided.repository.list_drawing_attempts(session_id))


def test_los_resultados_se_guardan_en_la_base(env):  # noqa: F811
    assert isinstance(env.guided.repository, PostgresGuidedSessionRepository)
    session_id = full_session(env)
    repository = env.guided.repository
    assert len(repository.list_drawing_attempts(session_id)) == 2           # el último no empezó
    assert len(repository.list_game_attempts(session_id)) == 3
    assert len(repository.list_practice_results(session_id)) == 1


# --- Estadísticas -------------------------------------------------------------------------------


def test_las_estadisticas_cuentan_dibujos_y_juegos_por_sesion(env):  # noqa: F811
    full_session(env)
    mine = get(env, "/statistics").json()
    drawing, games = mine["drawing"], mine["games"]
    assert drawing["sessions"] == 1 and drawing["totals"]["exercises"] == 2
    assert drawing["totals"]["answered"] == 1 and drawing["totals"]["skipped"] == 1
    assert drawing["by_expression"] == [{"expression": "happiness", "count": 1}]
    assert drawing["totals"]["sentence"] == "Se señaló una emoción en 1 de 2 dibujos."
    assert games["sessions"] == 1 and games["totals"]["games"] == 2 and games["totals"]["attempts"] == 3
    assert [row["game_type"] for row in games["by_type"]] == ["matching"]
    assert games["totals"]["completed"] == 1 and games["totals"]["stopped"] == 1
    # Sin filas por persona ni por cuenta.
    assert "by_user" not in drawing and "by_user" not in games
    group = get(env, "/statistics?scope=group", env.docente_a).json()
    assert group["drawing"]["sessions"] == 1 and group["games"]["totals"]["attempts"] == 3
    other = get(env, "/statistics?scope=group", env.docente_b).json()
    assert other["drawing"] is None and other["games"] is None


def test_el_aplicativo_movil_recibe_el_mismo_resumen(env, mobile):  # noqa: F811
    session_id = full_session(env)
    web = get(env, f"/sessions/{session_id}/metrics").json()["educational"]
    detail = mobile_get(mobile, f"/mobile/sessions/{session_id}", env.user_1.email)
    assert detail.status_code == 200 and detail.json()["metrics"]["educational"] == web
    statistics = mobile_get(mobile, "/mobile/statistics", env.user_1.email).json()
    assert statistics["drawing"]["totals"]["answered"] == 1 and statistics["games"]["totals"]["attempts"] == 3
