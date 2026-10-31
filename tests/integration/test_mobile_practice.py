"""Revisión 4.1 del contrato móvil: los resultados de práctica en lo que el
aplicativo ya consulta, sin rutas para conducir sesiones (SQLite en memoria, reloj
y analizador falsos; sin modelos ni imágenes de personas)."""
from __future__ import annotations

from emotv.domain.guided_session import PRACTICE_NOTICE
from tests.integration.test_guided_sessions import post
from tests.integration.test_mobile_api import get, mobile  # noqa: F401
from tests.integration.test_practice_api import practice, start
from tests.integration.test_practice_sessions import HAPPY, send
from tests.integration.test_practice_statistics import protocol, results
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_session_statistics import session


def practiced_session(env):  # noqa: F811
    """Conducida en la web: el primer ejercicio se logra, el segundo se salta."""
    session_id, token = start(env, practice(), practice("surprise"))
    send(env, token, HAPPY, count=6)
    send(env, token, HAPPY, count=5)
    assert post(env, session_id, "skip").status_code == 200
    return session_id


def test_el_detalle_de_la_sesion_trae_la_practica(env, mobile):  # noqa: F811
    session_id = practiced_session(env)
    detail = get(mobile, f"/mobile/sessions/{session_id}", "usuario1@example.com").json()
    block = detail["metrics"]["practice"]
    assert block["notice"] == PRACTICE_NOTICE
    assert block["totals"]["sentence"] == "Logró la expresión pedida en 1 de 1 ejercicio."
    assert (block["totals"]["skipped"], block["totals"]["exercises"]) == (1, 2)
    assert [item["outcome"] for item in block["exercises"]] == ["achieved", "skipped"]
    assert block["by_target"][0]["target_expression"] == "happiness"
    # Lo mismo que la web y sin tocar la coincidencia de estímulos.
    web = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    assert block == web["practice"]
    assert detail["metrics"]["totals"]["emotional_stimuli"] == 0
    lane = detail["timeline"]["lanes"]["stimuli"]
    assert [(item["kind"], item["target_expression"], item["outcome"]) for item in lane] == [
        ("practice", "happiness", "achieved"), ("practice", "surprise", "skipped")]
    # El docente del grupo también lo ve; el resto, no.
    assert get(mobile, f"/mobile/sessions/{session_id}", "docente.a@example.com").json()["metrics"]["practice"] == block
    for email in ("usuario2@example.com", "docente.b@example.com"):
        assert get(mobile, f"/mobile/sessions/{session_id}", email).status_code == 403


def test_una_sesion_sin_ejercicios_trae_practica_nula(env, mobile):  # noqa: F811
    item = session(env, env.user_1)
    detail = get(mobile, f"/mobile/sessions/{item.id}", "usuario1@example.com").json()
    assert detail["metrics"]["practice"] is None


def test_las_estadisticas_traen_la_practica_sin_desglose_por_usuario(env, mobile):  # noqa: F811
    family = protocol(env, env.user_1, "Alegría y sorpresa", "happiness", "surprise")
    first = session(env, env.user_1, protocol=family, audience="infantil")
    results(env, first, ("happiness", "achieved", 2.0, True), ("surprise", "timed_out", None, False))
    second = session(env, env.user_1, day=1, protocol=family, audience="infantil")
    results(env, second, ("happiness", "achieved", 4.0, True), ("surprise", "skipped", None, True))

    mine = get(mobile, "/mobile/statistics", "usuario1@example.com").json()
    block = mine["practice"]
    assert set(block) == {"sessions", "totals", "by_protocol", "by_target", "notice"}
    assert block["notice"] == PRACTICE_NOTICE and block["sessions"] == 2
    assert block["totals"]["sentence"] == "Logró la expresión pedida en 2 de 3 ejercicios."
    assert block["totals"]["average_seconds_to_achieve"] == 3.0
    assert [row["name"] for row in block["by_protocol"]] == ["Alegría y sorpresa"]
    assert [row["target_expression"] for row in block["by_target"]] == ["happiness", "surprise"]
    # Aparte de la coincidencia de estímulos; las claves de la revisión 4 siguen iguales.
    assert mine["coincidence"] == {"compared": 0, "matched": 0}
    assert set(mine) == {"scope", "notice", "few_sessions_notice", "sessions", "expressions", "coincidence", "practice"}

    group = get(mobile, "/mobile/statistics", "docente.a@example.com", scope="group").json()
    assert group["practice"]["totals"] == block["totals"]
    assert "by_user" not in group and "by_user" not in group["practice"]
    assert "usuario1@example.com" not in str(group)
    assert get(mobile, "/mobile/statistics", "docente.b@example.com", scope="group").json()["practice"] is None


def test_sin_ejercicios_las_estadisticas_traen_practica_nula(env, mobile):  # noqa: F811
    session(env, env.user_1)
    assert get(mobile, "/mobile/statistics", "usuario1@example.com").json()["practice"] is None


def test_el_aplicativo_sigue_sin_conducir_sesiones_ni_recibir_cuadros(mobile):  # noqa: F811
    paths = mobile.client.app.openapi()["paths"]
    assert "/mobile/statistics" in paths and "/mobile/sessions/{session_id}" in paths
    assert not [path for path in paths if any(word in path for word in (
        "frame", "practice", "calibration", "advance", "skip", "stop", "guided", "participant", "markers"))]
    writes = {path for path, operations in paths.items()
              if set(operations) & {"post", "put", "patch", "delete"}}
    assert writes == {"/mobile/auth/login", "/mobile/auth/refresh", "/mobile/auth/logout",
                      "/mobile/sessions/{session_id}/report", "/mobile/reports/{report_id}",
                      "/mobile/reports/{report_id}/submit", "/mobile/reports/{report_id}/comments",
                      "/mobile/reports/{report_id}/return", "/mobile/reports/{report_id}/approve"}
