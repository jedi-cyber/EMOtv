"""«Responde con la cara»: en los juegos de emparejar y «Busca la misma emoción», la
persona responde poniendo la cara de la emoción y la cámara marca la opción que
coincide, como si la hubiera tocado. Solo las cinco expresiones que estima EMOtv;
sin cámara se responde con botones. Los niveles solo los ve quien conduce.
(SQLite en memoria, reloj y analizador falsos; sin modelos ni imágenes de personas.)"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from emotv.domain.guided_session import GAME_FACE_PROMPT, SIMILAR_FACE_PROMPT, FrameAssessment
from emotv.domain.protocol import CAMERA_PRACTICE_TARGETS, FACE_ANSWER_GRACE_SECONDS, ProtocolStep, StepKind
from tests.integration import test_similar_game as similar_game
from tests.integration.test_guided_sessions import post, state, view, wait
from tests.integration.test_matching_game import act, bank, game, results, save, start
from tests.integration.test_practice_sessions import send
from tests.integration.test_practice_persistence import engine  # noqa: F401
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401

FIVE_AND_MORE = ("happiness", "sadness", "anger", "fear", "disgust")


def face_game(**fields):
    return {**game(rounds=2, options=2), "answer_by_face": True, **fields}


def face(expression):
    """Lo que estima el analizador falso: la persona sostiene esa cara."""
    return FrameAssessment((), expression, 0.95, {expression: 0.95, "contempt": 0.05})


def hold(env, token, expression, seconds=FACE_ANSWER_GRACE_SECONDS + 4):  # noqa: F811
    send(env, token, face(expression), count=int(seconds / 0.5))


# --- Dominio y protocolo ------------------------------------------------------------------

def test_solo_un_juego_se_responde_con_la_cara():
    item = ProtocolStep(None, 20, 0, kind=StepKind.GAME, game_type="matching", rounds=2, option_count=2,
                        answer_by_face=True)
    assert item.wants_camera and not item.uses_camera     # sin cámara se juega igual, con botones
    with pytest.raises(ValueError):
        ProtocolStep(None, 60, 0, kind=StepKind.DRAWING, answer_by_face=True)
    with pytest.raises(ValueError):
        ProtocolStep(None, 20, 0, kind=StepKind.GAME, game_type="matching", rounds=2, option_count=2,
                     answer_by_face=True, show_expression=True)


def test_el_protocolo_guarda_la_opcion_y_solo_usa_las_cinco_expresiones(env):  # noqa: F811
    bank(env, FIVE_AND_MORE)
    response = save(env, [face_game(rounds=3)])
    assert response.status_code == 201, response.text
    step = response.json()["steps"][0]
    assert step["answer_by_face"] is True and response.json()["uses_camera"] is True
    stored = {item["id"]: item["expected_expression"]
              for item in env.client.get("/stimuli", headers=headers(env, env.user_1)).json()}
    assert all(stored[item] in ("happiness", "sadness", "anger") for item in step["game_stimulus_ids"])
    assert save(env, [{"kind": "drawing", "exposure_seconds": 60, "answer_by_face": True}]).status_code == 422


def test_sin_imagenes_de_las_cinco_expresiones_no_se_guarda(env):  # noqa: F811
    bank(env, ("fear", "disgust"))
    response = save(env, [face_game()])
    assert response.status_code == 422
    assert "neutral, felicidad, sorpresa, tristeza o enojo" in response.text


# --- La sesión ------------------------------------------------------------------------------

def test_la_camara_marca_la_opcion_que_sostiene_la_cara(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, face_game())
    participant = view(env, token).json()
    assert participant["capture_frames"] is True
    shown = participant["game"]
    assert shown["answers_by_face"] is True and shown["message"] == GAME_FACE_PROMPT
    # Las opciones no se tocan: las marca la cámara.
    assert act(env, token, "answer", state(env, session_id)["game"]["target_expression"]).status_code == 409

    info = state(env, session_id)["game"]
    target = info["target_expression"]
    other = next(item for item in info["options"] if item != target)

    # Una cara equivocada marca esa opción: «Mira otra vez» y ya no se ofrece.
    hold(env, token, other)
    shown = view(env, token).json()["game"]
    assert shown["state"] == "retry"
    assert next(item for item in shown["options"] if item["key"] == other)["available"] is False

    # La cara de la emoción de la imagen la empareja.
    conductor = state(env, session_id)["game"]
    assert conductor["answers_by_face"] is True
    hold(env, token, target)
    assert view(env, token).json()["game"]["state"] == "matched"
    assert state(env, session_id)["game"]["face_levels"] == []   # la ronda ya terminó

    # La pantalla de la persona nunca recibe niveles ni la expresión estimada.
    text = json.dumps(view(env, token).json()).lower()
    assert "level" not in text and "probab" not in text and "confidence" not in text


def test_los_primeros_segundos_no_cuentan(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, face_game())
    target = state(env, session_id)["game"]["target_expression"]
    send(env, token, face(target), count=int(FACE_ANSWER_GRACE_SECONDS / 0.5) - 1)
    assert view(env, token).json()["game"]["state"] == "playing"
    assert state(env, session_id)["game"]["face_levels"] == []
    hold(env, token, target)
    assert view(env, token).json()["game"]["state"] == "matched"


def test_las_distractoras_tambien_son_de_las_cinco_expresiones(env):  # noqa: F811
    # Una opción de asco, miedo o desprecio no se podría marcar con la cara.
    bank(env)
    session_id, token = start(env, {**face_game(), **game(rounds=3, options=4), "answer_by_face": True})
    for _ in range(3):
        options = state(env, session_id)["game"]["options"]
        assert len(options) == 4 and set(options) <= set(CAMERA_PRACTICE_TARGETS)
        hold(env, token, state(env, session_id)["game"]["target_expression"])
        assert act(env, token, "next").status_code == 200


def test_quien_conduce_ve_el_nivel_de_cada_opcion(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, face_game())
    target = state(env, session_id)["game"]["target_expression"]
    send(env, token, face(target), count=int(FACE_ANSWER_GRACE_SECONDS / 0.5) + 2)
    levels = {item["key"]: item["level"] for item in state(env, session_id)["game"]["face_levels"]}
    assert levels[target] > 0 and all(value == 0 for key, value in levels.items() if key != target)


def test_quien_conduce_puede_registrar_la_respuesta(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, face_game())
    target = state(env, session_id)["game"]["target_expression"]
    response = env.client.post(f"/guided-sessions/{session_id}/game", headers=headers(env, env.user_1),
                               json={"action": "answer", "expression": target})
    assert response.status_code == 200, response.text
    assert view(env, token).json()["game"]["state"] == "matched"


def test_sin_camara_se_responde_con_botones(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, face_game())
    assert post(env, session_id, "continue-without-camera").status_code == 200
    shown = view(env, token).json()["game"]
    assert shown["answers_by_face"] is False and shown["message"] is None
    assert act(env, token, "answer", state(env, session_id)["game"]["target_expression"]).status_code == 200


def test_el_juego_completo_guarda_solo_contadores(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, face_game())
    for _ in range(2):
        hold(env, token, state(env, session_id)["game"]["target_expression"])
        assert act(env, token, "next").status_code == 200
    (result,) = results(env, session_id)
    assert (result.rounds_done, result.matched, result.first_try) == (2, 2, 2)
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    assert metrics["game"]["exercises"][0]["answer_by_face"] is True


def test_busca_la_misma_emocion_con_la_cara(env):  # noqa: F811
    similar_game.bank(env)
    session_id, token = similar_game.start(env, {**similar_game.similar(), "answer_by_face": True})
    shown = view(env, token).json()["game"]
    assert shown["answers_by_face"] is True and shown["message"] == SIMILAR_FACE_PROMPT
    info = similar_game.round_info(env, session_id)
    hold(env, token, info["target_expression"])
    shown = view(env, token).json()["game"]
    assert shown["state"] == "matched" and shown["answer"] == similar_game.correct_key(info)


# --- Migración 52 ---------------------------------------------------------------------------

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261125_52_game_answer_by_face.py"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_20261125_52", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, name: str) -> None:  # noqa: F811
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), name)()


def test_la_migracion_52_sigue_a_la_51():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261125_52", "20261124_51")


def test_la_migracion_52_vuelve_atras_y_otra_vez_adelante(engine):  # noqa: F811
    columns = lambda: {item["name"] for item in inspect(engine).get_columns("protocol_steps")}  # noqa: E731
    assert "answer_by_face" in columns()
    _run(engine, "downgrade")
    assert "answer_by_face" not in columns()
    _run(engine, "upgrade")
    assert "answer_by_face" in columns()
