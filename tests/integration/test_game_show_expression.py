"""«Reconoce y luego muéstrala»: al terminar cada ronda de un juego, la persona pone
la cara de la emoción de la ronda y la cámara estima si la sostiene. Solo quien
conduce ve el resultado; la persona ve un mensaje amable, el mismo la sostenga o no.
(SQLite en memoria, reloj y analizador falsos; sin modelos ni imágenes de personas.)"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from emotv.domain.guided_session import GAME_SHOW_THANKS, FrameAssessment, GameResult
from emotv.domain.protocol import GAME_SHOW_SECONDS, ProtocolStep, StepKind
from tests.integration.test_guided_sessions import frame, post, state, view, wait
from tests.integration.test_matching_game import act, bank, game, results, start
from tests.integration.test_practice_sessions import NEUTRAL, send
from tests.integration.test_practice_persistence import engine  # noqa: F401
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401


def show_game(**fields):
    return {**game(rounds=2, options=2), "show_expression": True, **fields}


def assessment_for(expression):
    return FrameAssessment((), expression, 0.95, {expression: 0.95, "neutral": 0.05})


def solve_round(env, session_id, token):  # noqa: F811
    info = state(env, session_id)["game"]
    assert act(env, token, "answer", info["target_expression"]).status_code == 200
    return info["target_expression"]


def test_solo_un_juego_pide_mostrar_la_emocion():
    item = ProtocolStep(None, 20, 0, kind=StepKind.GAME, game_type="matching", rounds=3, option_count=2,
                        show_expression=True)
    assert item.wants_camera and not item.uses_camera       # sin cámara se juega igual
    assert item.seconds_limit == (20 + GAME_SHOW_SECONDS) * 3
    with pytest.raises(ValueError):
        ProtocolStep(None, 60, 0, kind=StepKind.DRAWING, show_expression=True)
    with pytest.raises(ValueError):
        GameResult(id="g", session_id="s", step_index=0, game_type="matching", outcome="completed",
                   started_at=_now(), ended_at=_now(), rounds_total=1, rounds_done=1, matched=1,
                   faces_asked=1, faces_shown=2)


def _now():
    from datetime import datetime, timezone
    return datetime(2026, 11, 24, tzinfo=timezone.utc)


def test_el_protocolo_guarda_la_opcion_y_pide_la_camara(env):  # noqa: F811
    bank(env)
    response = env.client.post("/protocols", headers=headers(env, env.user_1), json={
        "name": "Reconoce y muestra", "description": "", "for_children": False, "steps": [show_game()]})
    assert response.status_code == 201, response.text
    assert response.json()["steps"][0]["show_expression"] is True
    assert response.json()["uses_camera"] is True
    assert env.client.post("/protocols", headers=headers(env, env.user_1), json={
        "name": "Mal", "description": "", "for_children": False,
        "steps": [{"kind": "drawing", "exposure_seconds": 60, "show_expression": True}]}).status_code == 422


def test_reconoce_y_luego_muestrala_solo_quien_conduce_ve_el_resultado(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, show_game())

    # Ronda 1: la encuentra; mientras juega, los cuadros solo sirven para la lectura
    # en vivo de quien conduce (no cuentan para el juego).
    assert view(env, token).json()["capture_frames"] is True
    target = solve_round(env, session_id, token)
    shown = view(env, token).json()["game"]
    assert shown["state"] == "matched" and shown["asks_face"] is True
    assert act(env, token, "next").status_code == 200

    # Pone la cara: la pantalla envía cuadros y muestra solo un mensaje amable.
    participant = view(env, token).json()
    assert participant["capture_frames"] is True
    assert participant["game"]["state"] == "show"
    assert participant["game"]["message"].startswith("Ahora pon tú esa cara")
    conductor = state(env, session_id)["game"]
    assert conductor["face"]["showing"] is True and conductor["faces_asked"] == 1

    send(env, token, assessment_for(target), count=6)
    participant = view(env, token).json()["game"]
    assert participant["state"] == "showed" and participant["message"] == GAME_SHOW_THANKS
    # La persona nunca ve el nivel, si lo logró ni la expresión estimada.
    text = str(participant).lower()
    assert "level" not in text and "achieved" not in text and "confidence" not in text
    conductor = state(env, session_id)["game"]
    assert conductor["face"]["achieved"] is True and conductor["faces_shown"] == 1

    # Ronda 2: no la sostiene; vence el tiempo y ve el mismo mensaje amable.
    assert act(env, token, "next").status_code == 200
    solve_round(env, session_id, token)
    assert act(env, token, "next").status_code == 200
    send(env, token, NEUTRAL, count=2)
    wait(env, GAME_SHOW_SECONDS)
    participant = view(env, token).json()["game"]
    assert participant["state"] == "showed" and participant["message"] == GAME_SHOW_THANKS
    assert state(env, session_id)["game"]["face"]["achieved"] is False
    assert act(env, token, "next").status_code == 200

    (result,) = results(env, session_id)
    assert (result.matched, result.faces_asked, result.faces_shown) == (2, 2, 1)
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    exercise = metrics["game"]["exercises"][0]
    assert exercise["face_sentence"] == ("Al pedirle poner la cara, la cámara estimó la expresión pedida en 1 de "
                                         "2 rondas. Es una estimación, no una valoración.")


def test_sin_la_opcion_el_juego_no_pide_la_cara(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2, options=2))
    solve_round(env, session_id, token)
    assert view(env, token).json()["game"]["asks_face"] is False
    assert act(env, token, "next").status_code == 200
    assert view(env, token).json()["game"]["state"] == "playing"
    frame(env, token)   # un cuadro en un juego sin la opción se descarta
    assert state(env, session_id)["game"]["face"] is None


def test_sin_camara_se_juega_sin_pedir_la_cara(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, show_game())
    assert post(env, session_id, "continue-without-camera").status_code == 200
    solve_round(env, session_id, token)
    assert view(env, token).json()["game"]["asks_face"] is False
    assert act(env, token, "next").status_code == 200
    assert view(env, token).json()["game"]["state"] == "playing"


def test_las_emociones_que_emotv_no_estima_no_piden_la_cara(env):  # noqa: F811
    bank(env, ("fear", "disgust"))
    session_id, token = start(env, show_game())
    solve_round(env, session_id, token)
    assert view(env, token).json()["game"]["asks_face"] is False
    assert act(env, token, "next").status_code == 200
    assert view(env, token).json()["game"]["state"] == "playing"


# --- Migración 51 ---------------------------------------------------------------------------

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261124_51_game_show_expression.py"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_20261124_51", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, name: str) -> None:  # noqa: F811
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), name)()


def test_la_migracion_51_sigue_a_la_50():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261124_51", "20261124_50")


def test_la_migracion_51_vuelve_atras_y_otra_vez_adelante(engine):  # noqa: F811
    columns = lambda table: {item["name"] for item in inspect(engine).get_columns(table)}  # noqa: E731
    assert "show_expression" in columns("protocol_steps") and "faces_asked" in columns("game_results")
    _run(engine, "downgrade")
    assert "show_expression" not in columns("protocol_steps")
    assert not {"faces_asked", "faces_shown"} & columns("game_results")
    _run(engine, "upgrade")
    assert "show_expression" in columns("protocol_steps") and "faces_shown" in columns("game_results")
    checks = {item["name"] for item in inspect(engine).get_check_constraints("game_results")}
    assert "ck_game_results_faces" in checks
