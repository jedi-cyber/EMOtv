"""Pasos de reconocimiento («¿Qué emoción es?») en la sesión guiada: armado del
protocolo, opciones, respuesta de la persona o de quien conduce, tiempo vencido,
saltar, detener, métricas, estadísticas y eliminación (SQLite en memoria, reloj
falso y analizador falso; sin modelos ni imágenes de personas)."""
from __future__ import annotations

from emotv.domain.guided_session import (
    RECOGNITION_NOTICE,
    RECOGNITION_QUESTION,
    RecognitionAnswerer,
    RecognitionOutcome,
)
from tests.integration.test_guided_sessions import (
    begin_steps,
    frame,
    guided,
    post,
    protocol,
    state,
    step,
    stimuli,
    view,
    wait,
)
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import approve, upload_stimulus


def recognition(stimulus, exposure=10, options=None):
    body = {"kind": "recognition", "stimulus_id": stimulus["id"], "exposure_seconds": exposure}
    if options is not None:
        body["option_count"] = options
    return body


def sad_stimulus(env):  # noqa: F811
    return approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Niño triste",
                                                       expected_expression="sadness"))


def start(env, *steps):  # noqa: F811
    """Sesión en el primer paso (calibrada si algún paso usa la cámara)."""
    session_id, token = guided(env, protocol(env, list(steps)))
    begin_steps(env, session_id, token)
    current = state(env, session_id)
    assert current["phase"] == "stimuli" and current["step_index"] == 0
    return session_id, token


def answer(env, token, expression):  # noqa: F811
    return env.client.post(f"/participant-view/{token}/answer", json={"expression": expression})


def results(env, session_id):  # noqa: F811
    return env.guided.repository.list_recognition_results(session_id)


# --- Armado del protocolo -------------------------------------------------------------


def test_la_respuesta_correcta_sale_de_la_imagen_y_hay_tres_opciones_por_defecto(env):  # noqa: F811
    sad = sad_stimulus(env)
    # Aunque se envíe otra expresión, el servidor usa la esperada de la imagen.
    item = protocol(env, [{**recognition(sad), "target_expression": "happiness"}])
    [saved] = item["steps"]
    assert saved["kind"] == "recognition" and saved["target_expression"] == "sadness"
    assert saved["option_count"] == 3 and saved["capture_after_seconds"] == 0


def test_un_reconocimiento_necesita_una_imagen_emocional_con_expresion_y_entre_2_y_4_opciones(env):  # noqa: F811
    _, abstract = stimuli(env)
    body = {"name": "Reconocer", "description": "", "for_children": False}
    response = env.client.post("/protocols", headers=headers(env, env.user_1),
                               json={**body, "steps": [recognition(abstract)]})
    assert response.status_code == 422 and "imagen emocional" in response.json()["detail"]
    sad = sad_stimulus(env)
    for count in (1, 5):
        response = env.client.post("/protocols", headers=headers(env, env.user_1),
                                   json={**body, "steps": [recognition(sad, options=count)]})
        assert response.status_code == 422 and "entre 2 y 4 opciones" in response.json()["detail"]
    response = env.client.post("/protocols", headers=headers(env, env.user_1),
                               json={**body, "steps": [{**recognition(sad), "stimulus_id": None}]})
    assert response.status_code == 422


# --- Sesión ---------------------------------------------------------------------------------


def test_la_persona_elige_una_opcion_lee_la_emocion_y_el_paso_avanza(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, recognition(sad, options=4))
    shown = view(env, token).json()
    block = shown["recognition"]
    assert block["question"] == RECOGNITION_QUESTION and block["chosen"] is None and block["message"] is None
    keys = [option["key"] for option in block["options"]]
    assert len(keys) == 4 and len(set(keys)) == 4 and "sadness" in keys and "contempt" not in keys
    assert {option["label"] for option in block["options"]} >= {"Tristeza"}
    # Se muestra la imagen, sin analizar la cámara y sin la práctica.
    assert shown["stimulus"] is not None and shown["capture_frames"] is False and "practice" not in shown
    assessed = env.frames_assessed
    frame(env, token)
    assert env.frames_assessed == assessed
    # Las mismas opciones, en el mismo orden, en cada consulta.
    assert [option["key"] for option in view(env, token).json()["recognition"]["options"]] == keys

    wait(env, 3)
    other = next(key for key in keys if key != "sadness")
    assert answer(env, token, "contempt").status_code == 422          # no se mostró
    assert answer(env, token, other).json() == {"received": True}
    assert answer(env, token, "sadness").status_code == 409           # ya respondió
    block = view(env, token).json()["recognition"]
    # Nombra la emoción de la imagen, sin decir si acertó.
    assert block["chosen"] == other and block["message"] == "Es tristeza"
    [item] = results(env, session_id)
    assert item.outcome is RecognitionOutcome.ANSWERED and item.chosen_expression == other
    assert item.matched is False and item.seconds_to_answer == 3.0
    assert item.answered_by is RecognitionAnswerer.PARTICIPANT and list(item.options) == keys
    conductor = state(env, session_id)
    assert conductor["recognition"]["chosen_expression"] == other
    assert conductor["recognition"]["target_expression"] == "sadness"
    assert conductor["recognition_results"][0]["matched"] is False
    assert conductor["captures"] == []                                 # el reconocimiento no crea capturas
    wait(env, 2.1)                                                     # pausa de 2 s
    assert state(env, session_id)["phase"] == "finished"


def test_al_vencer_el_tiempo_se_registra_sin_respuesta_y_se_nombra_la_emocion(env):  # noqa: F811
    sad = sad_stimulus(env)
    emotional, _ = stimuli(env)
    session_id, token = start(env, recognition(sad, exposure=5, options=2), recognition(emotional))
    wait(env, 5.5)
    current = view(env, token).json()["recognition"]
    assert current["message"] == "Es tristeza" and current["chosen"] is None
    assert len(current["options"]) == 2
    assert answer(env, token, "sadness").status_code == 409
    [item] = results(env, session_id)
    assert item.outcome is RecognitionOutcome.TIMED_OUT and item.chosen_expression is None
    assert item.seconds_to_answer is None and item.answered_by is None and item.matched is None
    wait(env, 2)
    assert state(env, session_id)["step_index"] == 1
    assert view(env, token).json()["recognition"]["message"] is None


def test_quien_conduce_registra_la_opcion_que_la_persona_senalo(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, recognition(sad))
    wait(env, 1.5)
    assert post(env, session_id, "recognition", {"expression": "sadness"}).status_code == 200
    [item] = results(env, session_id)
    assert item.answered_by is RecognitionAnswerer.CONDUCTOR and item.matched is True
    assert item.seconds_to_answer == 1.5
    # Otra cuenta no controla la sesión.
    assert post(env, session_id, "recognition", {"expression": "sadness"}, user=env.user_2).status_code in (403, 404)


def test_saltar_o_detener_un_reconocimiento_lo_registra(env):  # noqa: F811
    sad = sad_stimulus(env)
    emotional, _ = stimuli(env)
    session_id, token = start(env, recognition(sad), recognition(emotional), step(emotional))
    wait(env, 1)
    assert post(env, session_id, "skip").status_code == 200
    assert results(env, session_id)[0].outcome is RecognitionOutcome.SKIPPED
    wait(env, 1)
    assert env.client.post(f"/participant-view/{token}/stop").json() == {"stopped": True}
    assert [item.outcome for item in results(env, session_id)] == [RecognitionOutcome.SKIPPED,
                                                                    RecognitionOutcome.STOPPED]


# --- Métricas, estadísticas y eliminación ----------------------------------------------------


def test_las_metricas_y_las_estadisticas_describen_las_respuestas(env):  # noqa: F811
    sad = sad_stimulus(env)
    emotional, _ = stimuli(env)
    session_id, token = start(env, recognition(sad), recognition(emotional, exposure=4), step(emotional))
    wait(env, 2)
    assert answer(env, token, "sadness").status_code == 200
    wait(env, 2.1)
    assert state(env, session_id)["step_index"] == 1
    wait(env, 6.5)                                                     # vence sin respuesta
    assert state(env, session_id)["step_index"] == 2
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    block = metrics["recognition"]
    assert block["notice"] == RECOGNITION_NOTICE
    assert block["totals"]["sentence"] == "Eligió la emoción de la imagen en 1 de 2 ejercicios."
    assert block["totals"]["timed_out"] == 1 and block["totals"]["average_seconds_to_answer"] == 2.0
    assert [row["target_expression"] for row in block["by_target"]] == ["happiness", "sadness"]
    # Las imágenes del reconocimiento no cuentan en la coincidencia de la expresión estimada.
    assert [row["step_index"] for row in metrics["emotional"]] == [2]
    timeline = env.client.get(f"/sessions/{session_id}/timeline", headers=headers(env, env.user_1)).json()
    lane = [item for item in timeline["lanes"]["stimuli"] if item["kind"] == "recognition"]
    assert [item["outcome"] for item in lane] == ["answered", "timed_out"]

    statistics = env.client.get("/statistics", headers=headers(env, env.user_1)).json()
    assert statistics["recognition"]["sessions"] == 1
    assert statistics["recognition"]["totals"]["matched"] == 1


def test_eliminar_la_sesion_borra_los_reconocimientos(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, recognition(sad))
    answer(env, token, "sadness")
    post(env, session_id, "stop", {"reason": "conductor"})
    response = env.client.post(f"/sessions/{session_id}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 200, response.text
    assert response.json()["counts"]["recognition_results"] == 1
    assert results(env, session_id) == ()
