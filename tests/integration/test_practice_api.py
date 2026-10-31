"""Ejercicios de práctica por la API: armado del protocolo, vista de quien conduce,
interruptor de la señal y permisos (SQLite en memoria, reloj y analizador falsos;
sin modelos ni imágenes de personas)."""
from __future__ import annotations

import pytest

from tests.integration.test_guided_sessions import frame, guided, post, state, view, wait
from tests.integration.test_practice_sessions import HAPPY, NEUTRAL, send
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import approve, upload_stimulus


def practice(target="happiness", hold=2, max_seconds=20, illustration=None):
    item = {"kind": "practice", "target_expression": target, "hold_seconds": hold, "exposure_seconds": max_seconds}
    if illustration is not None:
        item["stimulus_id"] = illustration["id"]
    return item


def body(*steps, for_children=False):
    return {"name": "Práctica", "description": "", "for_children": for_children, "steps": list(steps)}


def create(env, *steps, for_children=False, user=None):  # noqa: F811
    return env.client.post("/protocols", headers=headers(env, user or env.user_1),
                           json=body(*steps, for_children=for_children))


def start(env, *steps):  # noqa: F811
    """Sesión con protocolo de prácticas armado por la API, ya calibrada y en el primer ejercicio."""
    response = create(env, *steps)
    assert response.status_code == 201, response.text
    session_id, token = guided(env, response.json())
    env.frame_result = NEUTRAL
    assert post(env, session_id, "calibration").status_code == 200
    for _ in range(5):
        frame(env, token)
        wait(env, 0.6)
    wait(env, 0.5)
    frame(env, token)
    assert state(env, session_id)["phase"] == "stimuli"
    return session_id, token


# --- Armado del protocolo ------------------------------------------------------------------


def test_el_editor_recibe_lo_que_propone_el_servidor(env):  # noqa: F811
    for user in (env.user_1, env.docente_a):
        response = env.client.get("/protocols/practice-defaults", headers=headers(env, user))
        assert response.status_code == 200
        assert response.json() == {"hold_seconds": 2, "max_seconds": 20, "targets": [
            "neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]}
    for user in (env.admin, env.superadmin):
        assert env.client.get("/protocols/practice-defaults", headers=headers(env, user)).status_code == 403
    assert env.client.get("/protocols/practice-defaults").status_code == 401


def test_un_protocolo_con_ejercicios_se_guarda_y_se_devuelve(env):  # noqa: F811
    mild = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Leve"))
    response = create(env, practice(), practice("surprise", 3, 15, illustration=mild),
                      {"stimulus_id": mild["id"], "exposure_seconds": 8, "capture_after_seconds": 4},
                      for_children=True)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert [step["kind"] for step in saved["steps"]] == ["practice", "practice", "stimulus"]
    assert saved["steps"][0]["stimulus_id"] is None and saved["steps"][1]["stimulus_id"] == mild["id"]
    assert (saved["steps"][1]["target_expression"], saved["steps"][1]["hold_seconds"]) == ("surprise", 3)
    assert saved["steps"][2]["target_expression"] is None and saved["needs_image"] is False
    listed = env.client.get("/protocols", headers=headers(env, env.user_1)).json()
    assert [step["kind"] for step in listed[0]["steps"]] == ["practice", "practice", "stimulus"]
    # Editar conserva los ejercicios.
    edited = env.client.put(f"/protocols/{saved['id']}", headers=headers(env, env.user_1),
                            json=body(practice("neutral", 1, 5), for_children=True))
    assert edited.status_code == 200, edited.text
    assert edited.json()["steps"][0]["target_expression"] == "neutral"


@pytest.mark.parametrize("step, message", [
    (practice(target="desprecio"), "expresión que se pide"),
    (practice(target=None), "expresión que se pide"),
    (practice(hold=0), "entre 1 y 10 segundos"),
    (practice(hold=11, max_seconds=30), "entre 1 y 10 segundos"),
    (practice(hold=5, max_seconds=5), "mayor que el tiempo de sostén"),
    ({**practice(), "capture_after_seconds": 3}, "captura automática"),
    ({**practice(), "record_verbal_response": True}, "respuesta verbal"),
    ({"stimulus_id": None, "exposure_seconds": 8, "capture_after_seconds": 4}, "indica un estímulo"),
    ({**practice(), "kind": "stimulus", "stimulus_id": "x"}, "no tiene expresión pedida"),
])
def test_las_reglas_del_dominio_llegan_como_mensajes_en_espanol(env, step, message):  # noqa: F811
    response = create(env, step)
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_un_protocolo_para_ninos_solo_admite_ilustraciones_para_ninos(env):  # noqa: F811
    moderate = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Moderado", intensity="moderate"))
    response = create(env, practice(illustration=moderate), for_children=True)
    assert response.status_code == 422 and "leves y aprobadas" in response.json()["detail"]
    assert create(env, practice(illustration=moderate)).status_code == 201


# --- Vista de quien conduce y señal -----------------------------------------------------------

def test_quien_conduce_ve_la_expresion_pedida_el_nivel_y_el_logro(env):  # noqa: F811
    session_id, token = start(env, practice(), practice("surprise"))
    current = state(env, session_id)
    assert current["steps"][0]["step_kind"] == "practice" and current["steps"][0]["target_expression"] == "happiness"
    assert current["practice"] == {"target_expression": "happiness", "hold_seconds": 2, "level": 0.0, "achieved": False}
    assert current["practice_feedback"] is True
    send(env, token, HAPPY, count=2)
    assert 0 < state(env, session_id)["practice"]["level"] < 1
    send(env, token, HAPPY, count=4)
    current = state(env, session_id)
    assert current["practice"]["achieved"] is True and current["practice"]["level"] == 1.0
    [result] = current["practice_results"]
    assert result["outcome"] == "achieved" and result["seconds_to_achieve"] == 2.5
    # Los marcadores siguen funcionando en un ejercicio.
    assert post(env, session_id, "markers", {"kind": "laughed"}).status_code == 201
    assert state(env, session_id)["markers"][0]["step_index"] == 0


def test_apagar_la_senal_deja_solo_la_instruccion_y_queda_en_el_resultado(env):  # noqa: F811
    session_id, token = start(env, practice())
    send(env, token, HAPPY, count=1)
    response = post(env, session_id, "practice-feedback", {"visible": False})
    assert response.status_code == 200 and response.json() == {"practice_feedback": False}
    shown = view(env, token).json()["practice"]
    assert shown["level"] is None and shown["instruction"] == "Muestra alegría"
    # Quien conduce sigue viendo el nivel en vivo.
    current = state(env, session_id)
    assert current["practice_feedback"] is False and current["practice"]["level"] is not None
    assert post(env, session_id, "skip").status_code == 200
    [result] = state(env, session_id)["practice_results"]
    assert result["outcome"] == "skipped" and result["feedback_visible"] is False
    assert post(env, session_id, "practice-feedback", {"visible": "quizás"}).status_code == 422


# --- Permisos -------------------------------------------------------------------------------

def test_solo_quien_conduce_maneja_el_ejercicio_y_su_docente_revisa(env):  # noqa: F811
    session_id, token = start(env, practice())
    send(env, token, HAPPY, count=6)
    for user in (env.docente_a, env.docente_b, env.user_2, env.admin, env.superadmin):
        assert env.client.get(f"/guided-sessions/{session_id}", headers=headers(env, user)).status_code == 403
        assert post(env, session_id, "practice-feedback", {"visible": False}, user=user).status_code == 403
        assert post(env, session_id, "skip", user=user).status_code == 403
    assert state(env, session_id)["practice_feedback"] is True
    review = env.client.get(f"/sessions/{session_id}/guided-results", headers=headers(env, env.docente_a))
    assert review.status_code == 200 and review.json()["practice_results"][0]["outcome"] == "achieved"
    for user in (env.user_2, env.docente_b, env.admin, env.superadmin):
        assert env.client.get(f"/sessions/{session_id}/guided-results", headers=headers(env, user)).status_code == 403
    assert env.client.post("/guided-sessions/no-existe/practice-feedback", headers=headers(env, env.user_1),
                           json={"visible": False}).status_code == 404


def test_un_protocolo_con_ejercicios_solo_lo_ven_quien_lo_armo_y_su_docente(env):  # noqa: F811
    saved = create(env, practice()).json()
    for user, visible in ((env.user_1, True), (env.docente_a, True), (env.user_2, False), (env.docente_b, False)):
        listed = {item["id"] for item in env.client.get("/protocols", headers=headers(env, user)).json()}
        assert (saved["id"] in listed) is visible
    # Solo quien lo armó lo edita.
    assert env.client.put(f"/protocols/{saved['id']}", headers=headers(env, env.docente_a),
                          json=body(practice())).status_code == 403
    assert env.client.put(f"/protocols/{saved['id']}", headers=headers(env, env.user_2),
                          json=body(practice())).status_code == 404
    for user in (env.admin, env.superadmin):
        assert create(env, practice(), user=user).status_code == 403
