"""Juego con cámara «Muestra la emoción»: rondas seguidas de práctica, una
estrella por ronda lograda y «Lograste X de Y caras» al final, sin puntos
(SQLite en memoria, reloj y analizador falsos; sin modelos ni imágenes de personas)."""
from __future__ import annotations

from tests.integration.test_guided_sessions import guided, post, state, view, wait
from tests.integration.test_practice_api import create
from tests.integration.test_practice_sessions import HAPPY, NEUTRAL, send
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401


def round_step(target, number, hold=2, max_seconds=20):
    return {"kind": "practice", "target_expression": target, "hold_seconds": hold,
            "exposure_seconds": max_seconds, "game_round": number}


def test_el_protocolo_guarda_las_rondas_del_juego(env):  # noqa: F811
    response = create(env, round_step("happiness", 1), round_step("sadness", 2), round_step("anger", 3))
    assert response.status_code == 201, response.text
    assert [step["game_round"] for step in response.json()["steps"]] == [1, 2, 3]
    stored = env.client.get(f"/protocols/{response.json()['id']}", headers=headers(env, env.user_1))
    if stored.status_code == 200:
        assert [step["game_round"] for step in stored.json()["steps"]] == [1, 2, 3]


def test_las_rondas_van_seguidas_y_son_al_menos_dos(env):  # noqa: F811
    assert create(env, round_step("happiness", 1)).status_code == 422
    assert create(env, round_step("happiness", 1), round_step("sadness", 3)).status_code == 422
    alone = create(env, round_step("happiness", 2), round_step("sadness", 3))
    assert alone.status_code == 422 and "seguidas" in alone.json()["detail"]
    # Solo las cinco expresiones que estima EMOtv.
    assert create(env, round_step("fear", 1), round_step("sadness", 2)).status_code == 422
    # Una ronda no lleva imagen ni imita un modelo.
    with_image = {**round_step("happiness", 1), "imitate": True, "stimulus_id": "x"}
    assert create(env, with_image, round_step("sadness", 2)).status_code == 422


def test_estrellas_por_ronda_y_lo_logrado_al_final(env):  # noqa: F811
    response = create(env, round_step("happiness", 1), round_step("sadness", 2, max_seconds=6),
                      round_step("happiness", 3))
    session_id, token = guided(env, response.json())
    env.frame_result = NEUTRAL
    assert post(env, session_id, "start").status_code == 200

    shown = view(env, token).json()
    assert shown["activity"]["name"] == "Muestra la emoción"
    game = shown["practice"]["camera_game"]
    assert game == {"round": 1, "rounds": 3, "stars": [None, None, None], "summary": None}
    assert state(env, session_id)["practice"]["camera_game"]["round"] == 1

    send(env, token, HAPPY, count=5)                          # ronda 1: lograda
    assert view(env, token).json()["practice"]["camera_game"]["stars"] == [True, None, None]
    wait(env, 2.1)
    assert state(env, session_id)["step_index"] == 1

    send(env, token, NEUTRAL, count=4)                        # ronda 2: no se logra
    wait(env, 4.5)                                            # venció el tiempo; en la pausa
    game = view(env, token).json()["practice"]["camera_game"]
    assert game["stars"] == [True, False, None] and game["summary"] is None
    wait(env, 2.1)
    assert state(env, session_id)["step_index"] == 2

    send(env, token, HAPPY, count=5)                          # ronda 3: lograda, la última
    shown = view(env, token).json()["practice"]
    assert shown["camera_game"]["stars"] == [True, False, True]
    assert shown["camera_game"]["summary"] == "Lograste 2 de 3 caras."
    # Lo que ve la persona: nunca puntos, la expresión detectada ni probabilidades.
    text = str(shown).lower()
    assert "punt" not in text and "probab" not in text and "confidence" not in text

    wait(env, 2.1)
    finished = state(env, session_id)
    assert finished["phase"] == "finished"
    assert [item["outcome"] for item in finished["practice_results"]] == ["achieved", "timed_out", "achieved"]
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    assert metrics is not None
