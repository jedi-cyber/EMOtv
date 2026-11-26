"""Paso «Usar el analizador»: sin imagen ni expresión pedida; la cámara estima la
expresión cada pocos segundos y quien conduce pasa al siguiente paso cuando termina
(SQLite en memoria, reloj y analizador falsos; sin modelos ni imágenes de personas)."""
from __future__ import annotations

from tests.integration.test_camera_game import round_step
from tests.integration.test_guided_sessions import guided, post, state, view, wait
from tests.integration.test_practice_api import create
from tests.integration.test_practice_sessions import HAPPY, send
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401


def analyzer_step(max_seconds=180):
    return {"kind": "analyzer", "exposure_seconds": max_seconds}


def test_el_protocolo_guarda_el_paso_del_analizador(env):  # noqa: F811
    response = create(env, analyzer_step(600))
    assert response.status_code == 201, response.text
    step = response.json()["steps"][0]
    assert step["kind"] == "analyzer" and step["exposure_seconds"] == 600 and step["stimulus_id"] is None


def test_el_paso_del_analizador_no_lleva_imagen_ni_expresion(env):  # noqa: F811
    assert create(env, {**analyzer_step(), "target_expression": "happiness"}).status_code == 422
    assert create(env, {**analyzer_step(), "stimulus_id": "x"}).status_code == 422
    assert create(env, {**analyzer_step(), "capture_after_seconds": 3}).status_code == 422
    assert create(env, analyzer_step(601)).status_code == 422
    # Los demás pasos siguen hasta 120 s.
    assert create(env, {"kind": "drawing", "exposure_seconds": 121}).status_code == 422


def test_captura_cada_pocos_segundos_y_quien_conduce_pasa_al_siguiente(env):  # noqa: F811
    response = create(env, analyzer_step(), round_step("happiness", 1), round_step("sadness", 2))
    session_id, token = guided(env, response.json())
    env.frame_result = HAPPY
    assert post(env, session_id, "start").status_code == 200

    shown = view(env, token).json()
    assert shown["activity"]["kind"] == "analyzer"
    assert shown["message"] == "Mira a la cámara y haz la expresión que te pidan."
    assert shown["capture_frames"] is True and shown["stimulus"] is None
    # La persona no ve la expresión estimada.
    assert "happiness" not in str(shown) and "confidence" not in str(shown)

    send(env, token, HAPPY, count=2)
    wait(env, 3.1)
    send(env, token, HAPPY, count=2)
    current = state(env, session_id)
    captures = [item for item in current["captures"] if item["step_index"] == 0]
    assert len(captures) == 2 and all(item["emotion"] == "happiness" for item in captures)

    assert post(env, session_id, "analyzer-done").status_code == 200
    after = state(env, session_id)
    assert after["step_index"] == 1
    assert after["steps_log"][0]["skipped"] is False
    # Solo se usa en «Usar el analizador».
    assert post(env, session_id, "analyzer-done").status_code == 409

    timeline = env.client.get(f"/sessions/{session_id}/timeline", headers=headers(env, env.user_1)).json()
    assert timeline is not None
