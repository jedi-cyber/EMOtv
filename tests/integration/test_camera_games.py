"""Juegos con cámara en el Analizador: sin protocolo propio, se elige «Empareja la
emoción» o «Busca la misma emoción» y EMOtv arma (o reutiliza) un protocolo de la
cuenta con ese juego, respondido con la cara. La sesión se crea después como con
cualquier protocolo: con su única confirmación y su código.
(SQLite en memoria; sin modelos ni imágenes de personas.)"""
from __future__ import annotations

from emotv.application.protocol_service import CAMERA_GAME_NAMES, CAMERA_GAME_ROUND_SECONDS
from tests.integration import test_similar_game as similar_game
from tests.integration.test_game_answer_by_face import FIVE_AND_MORE, hold
from tests.integration.test_guided_sessions import begin_steps, guided, state, view
from tests.integration.test_matching_game import bank
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401


def camera_game(env, game_type="matching", for_children=False, user=None):  # noqa: F811
    return env.client.post(f"/camera-games/{game_type}/protocol", headers=headers(env, user or env.user_1),
                           json={"for_children": for_children})


def test_arma_el_juego_con_la_cara_y_solo_las_cinco_expresiones(env):  # noqa: F811
    bank(env, FIVE_AND_MORE)
    response = camera_game(env)
    assert response.status_code == 200, response.text
    protocol = response.json()
    assert protocol["name"] == CAMERA_GAME_NAMES["matching"] and protocol["for_children"] is False
    assert protocol["owned_by_me"] is True and protocol["uses_camera"] is True
    assert protocol["camera_game"] == "matching"
    [step] = protocol["steps"]
    assert step["kind"] == "game" and step["game_type"] == "matching" and step["answer_by_face"] is True
    assert step["exposure_seconds"] == CAMERA_GAME_ROUND_SECONDS
    stored = {item["id"]: item["expected_expression"]
              for item in env.client.get("/stimuli", headers=headers(env, env.user_1)).json()}
    assert step["game_stimulus_ids"] and all(stored[item] in ("happiness", "sadness", "anger")
                                             for item in step["game_stimulus_ids"])


def test_reutiliza_el_de_la_cuenta_por_juego_y_publico(env):  # noqa: F811
    bank(env)
    first = camera_game(env).json()
    assert camera_game(env).json()["id"] == first["id"]
    children = camera_game(env, for_children=True).json()
    assert children["id"] != first["id"] and children["for_children"] is True
    assert camera_game(env, for_children=True).json()["id"] == children["id"]


def test_otro_juego_o_tipo_desconocido(env):  # noqa: F811
    bank(env)
    assert camera_game(env, "drawing").status_code == 422
    similar_game.bank(env)
    response = camera_game(env, "similar")
    assert response.status_code == 200, response.text
    assert response.json()["name"] == CAMERA_GAME_NAMES["similar"]
    assert response.json()["steps"][0]["answer_by_face"] is True


def test_sin_imagenes_de_las_cinco_expresiones_dice_que_falta(env):  # noqa: F811
    bank(env, ("fear", "disgust"))
    response = camera_game(env)
    assert response.status_code == 422
    assert "neutral, felicidad, sorpresa, tristeza o enojo" in response.text


def test_solo_usuarios_y_docentes(env):  # noqa: F811
    bank(env)
    assert camera_game(env, user=env.admin).status_code == 403
    assert camera_game(env, user=env.docente_a).status_code == 200


def test_la_sesion_sigue_como_con_cualquier_protocolo(env):  # noqa: F811
    bank(env)
    protocol = camera_game(env).json()
    session_id, token = guided(env, protocol)
    begin_steps(env, session_id, token)
    assert state(env, session_id)["phase"] == "stimuli"
    participant = view(env, token).json()
    assert participant["game"]["answers_by_face"] is True
    target = state(env, session_id)["game"]["target_expression"]
    hold(env, token, target)
    assert view(env, token).json()["game"]["state"] == "matched"
