"""Lectura en vivo para quien conduce: lo que estima la cámara sobre la expresión
visible de la persona, solo en la pantalla de quien conduce. Es la última
estimación en memoria: no se guarda y nunca llega a la pantalla de la persona.
(SQLite en memoria, reloj y analizador falsos; sin modelos ni imágenes de personas.)"""
from __future__ import annotations

import json

from tests.integration.test_guided_sessions import (begin_steps, frame, guided, protocol, state, step, stimuli,
                                                    view, wait)
from tests.integration.test_practice_sessions import HAPPY, NEUTRAL
from tests.integration.test_privacy_accounts import env  # noqa: F401


def test_quien_conduce_ve_lo_que_estima_la_camara_y_la_persona_no(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional, exposure=20, capture=10)]))
    begin_steps(env, session_id, token)
    assert state(env, session_id)["live_reading"] is None   # todavía no llegó ningún cuadro

    env.frame_result = HAPPY
    responses = []
    for _ in range(3):
        wait(env, 1)
        responses.append(frame(env, token).json())
        responses.append(view(env, token).json())
    reading = state(env, session_id)["live_reading"]
    assert reading["face_detected"] is True and reading["emotion"] == "happiness"
    assert reading["distribution"][0] == {"emotion": "happiness", "probability": 0.95}
    # La pantalla de la persona no recibe la lectura.
    text = json.dumps(responses)
    assert "live_reading" not in text and "happiness" not in text and "probability" not in text

    # Entre capturas no se guarda nada: la lectura vive solo en memoria.
    assert state(env, session_id)["captures"] == []

    # Cambia con el próximo cuadro (a lo sumo uno por segundo).
    env.frame_result = NEUTRAL
    wait(env, 1)
    frame(env, token)
    assert state(env, session_id)["live_reading"]["emotion"] == "neutral"

    # Sin cuadros nuevos, deja de mostrarse.
    wait(env, 4)
    assert state(env, session_id)["live_reading"] is None



def test_el_aviso_de_camara_se_quita_cuando_llegan_cuadros(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional, exposure=20, capture=10)]))
    assert env.client.post(f"/participant-view/{token}/camera-problem", json={"reason": "denied"}).status_code < 300
    assert state(env, session_id)["camera_problem"] == "denied"
    begin_steps(env, session_id, token)
    wait(env, 1)
    frame(env, token)      # la cámara funcionó al reintentar
    assert state(env, session_id)["camera_problem"] is None
