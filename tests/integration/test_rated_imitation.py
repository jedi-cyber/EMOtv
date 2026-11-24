"""«Juego: imita la cara» y dibujo con imagen.

- La persona ve una imagen y hace la misma cara; la cámara estima la expresión
  como en «Haz la misma cara». Al terminar, el paso espera a que quien conduce
  marque de 1 a 5 estrellas. Es su valoración: la persona no la ve y EMOtv no la
  calcula, no la suma ni la promedia.
- Un dibujo puede llevar una imagen que la persona mira antes de dibujar.

SQLite en memoria, reloj y analizador falsos; sin modelos ni imágenes de personas.
"""
from __future__ import annotations

import pytest

from emotv.domain.guided_session import PracticeResult
from emotv.domain.protocol import ProtocolStep
from tests.integration.test_guided_sessions import post, state, view, wait
from tests.integration.test_imitation_steps import get, happy_drawing, imitation
from tests.integration.test_practice_api import create, start
from tests.integration.test_practice_sessions import HAPPY, NEUTRAL, _no_forbidden, results, send
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401


def rated(stimulus, max_seconds=20):
    return {**imitation(stimulus), "exposure_seconds": max_seconds, "conductor_rating": True}


def rate(env, session_id, stars):  # noqa: F811
    return env.client.post(f"/guided-sessions/{session_id}/rating", headers=headers(env, env.user_1),
                           json={"stars": stars})


def test_el_protocolo_guarda_la_valoracion_solo_en_una_imitacion(env):  # noqa: F811
    stimulus = happy_drawing(env)
    response = create(env, rated(stimulus))
    assert response.status_code == 201, response.text
    [step] = response.json()["steps"]
    assert step["conductor_rating"] is True and step["imitate"] is True
    # Sin imagen que imitar no hay valoración.
    assert create(env, {"kind": "practice", "target_expression": "happiness", "hold_seconds": 2,
                        "exposure_seconds": 20, "conductor_rating": True}).status_code == 422
    with pytest.raises(ValueError):
        ProtocolStep.practice("happiness", 2, 20, conductor_rating=True)


def test_las_estrellas_van_de_1_a_5():
    base = dict(id="r", session_id="s", step_index=0, target_expression="happiness", outcome="timed_out",
                peak_level=0.1, relative_to_calibration=False, feedback_visible=True, analyzed_frames=1,
                flagged_frames=0, emotion_model_id="m", emotion_model_version="1")
    from tests.integration.test_practice_persistence import T0
    for wrong in (0, 6, True):
        with pytest.raises(ValueError):
            PracticeResult(**base, started_at=T0, ended_at=T0, conductor_stars=wrong)
    assert PracticeResult(**base, started_at=T0, ended_at=T0, conductor_stars=4).conductor_stars == 4


def test_el_paso_espera_la_valoracion_y_la_persona_no_la_ve(env):  # noqa: F811
    stimulus = happy_drawing(env)
    response = create(env, rated(stimulus), rated(stimulus, max_seconds=6))
    assert response.status_code == 201, response.text
    session_id, token = start(env, rated(stimulus), rated(stimulus, max_seconds=6))

    shown = view(env, token).json()
    assert shown["activity"]["name"] == "Imita la cara"
    assert shown["practice"]["instruction"] == "Haz la misma cara" and shown["stimulus"] is not None
    current = state(env, session_id)["practice"]
    assert current["rating"] == {"stars": None, "can_rate": False}
    # Mientras la persona imita, todavía no se valora.
    assert rate(env, session_id, 4).status_code == 409

    send(env, token, HAPPY, count=5)                      # la cámara la estima lograda
    assert state(env, session_id)["practice"]["rating"]["can_rate"] is True
    shown = view(env, token).json()
    assert shown["practice"]["message"] == "¡Gracias! Espera un momento."
    wait(env, 10)                                         # pasó la pausa: espera a quien conduce
    assert state(env, session_id)["step_index"] == 0

    assert rate(env, session_id, 6).status_code == 422
    assert rate(env, session_id, 4).status_code == 200
    assert state(env, session_id)["step_index"] == 1      # con la valoración, sigue
    shown = view(env, token).json()
    _no_forbidden(shown)
    assert "stars" not in str(shown) and "rating" not in str(shown) and "estrella" not in str(shown).lower()

    env.frame_result = NEUTRAL
    wait(env, 7)                                          # la segunda no se logra: también espera
    assert state(env, session_id)["step_index"] == 1
    assert state(env, session_id)["practice"]["rating"]["can_rate"] is True
    assert rate(env, session_id, 2).status_code == 200    # valorada durante la pausa: la pausa sigue
    wait(env, 2.1)
    assert state(env, session_id)["phase"] == "finished"

    assert [item.conductor_stars for item in results(env, session_id)] == [4, 2]
    practice = get(env, f"/sessions/{session_id}/metrics")["practice"]
    assert [item["conductor_stars"] for item in practice["exercises"]] == [4, 2]
    ratings = practice["conductor_ratings"]
    assert ratings["by_stars"] == [{"stars": 4, "count": 1}, {"stars": 2, "count": 1}]
    assert ratings["sentence"] == "Quien conduce valoró 2 de 2: 4 estrellas en 1, 2 estrellas en 1."
    assert "no un cálculo de EMOtv" in ratings["notice"]
    # Nada de sumas ni promedios.
    assert not any(key in ratings for key in ("average", "total", "score", "sum"))


def test_sin_juego_valorado_no_hay_bloque_de_valoraciones(env):  # noqa: F811
    session_id, token = start(env, imitation(happy_drawing(env)))
    send(env, token, HAPPY, count=5)
    assert rate(env, session_id, 3).status_code == 409
    assert "conductor_ratings" not in get(env, f"/sessions/{session_id}/metrics")["practice"]


def test_un_dibujo_puede_llevar_una_imagen(env):  # noqa: F811
    stimulus = happy_drawing(env)
    response = create(env, {"kind": "drawing", "exposure_seconds": 30, "stimulus_id": stimulus["id"]})
    assert response.status_code == 201, response.text
    assert response.json()["steps"][0]["stimulus_id"] == stimulus["id"]
    session_id, token = start(env, {"kind": "drawing", "exposure_seconds": 30, "stimulus_id": stimulus["id"]})
    assert post(env, session_id, "start").status_code in (200, 409)
    shown = view(env, token).json()
    assert shown["drawing"]["instruction"] == "Mira la imagen y dibuja una cara con la emoción que sientes."
    assert shown["stimulus"] is not None
    assert env.client.get(f"/participant-view/{token}/stimulus").status_code == 200
    # Sin imagen, la consigna de siempre.
    _, plain = start(env, {"kind": "drawing", "exposure_seconds": 30})
    assert view(env, plain).json()["drawing"]["instruction"] == "Dibuja una cara que muestre una emoción."
