"""Juego de emparejar expresiones (bloque 5): armado del protocolo con imágenes
elegidas del banco aprobado, rondas con ayuda, reintento y explicación, acciones
de quien conduce, tiempo vencido, repetir, saltar, detener, métricas sin
puntaje, línea de tiempo, eliminación y migración. Solo se guardan contadores.
(SQLite en memoria, reloj falso y analizador falso; sin modelos.)"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from emotv.domain.guided_session import (GAME_NOTICE, GAME_QUESTION, GAME_RETRY, GAME_RETRY_HELPED, GameOutcome,
                                         GameResult)
from emotv.domain.protocol import ProtocolStep, StepKind
from emotv.infrastructure.persistence.postgres_practice_repositories import PostgresProtocolRepository
from tests.integration.test_guided_sessions import begin_steps, frame, guided, post, state, view, wait
from tests.integration.test_practice_persistence import engine, factory, protocol  # noqa: F401
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import approve, upload_stimulus

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261106_41_matching_game.py"
BANK = ("happiness", "sadness", "anger")


def bank(env, expressions=BANK):  # noqa: F811
    return [approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title=f"Cara {expression}",
                                                       expected_expression=expression))
            for expression in expressions]


def game(rounds=3, options=2, seconds=30, ids=()):
    return {"kind": "game", "game_type": "matching", "rounds": rounds, "option_count": options,
            "exposure_seconds": seconds, "game_stimulus_ids": list(ids)}


def save(env, steps, for_children=False):  # noqa: F811
    return env.client.post("/protocols", headers=headers(env, env.user_1), json={
        "name": "Emparejar", "description": "", "for_children": for_children, "steps": steps})


def start(env, *steps):  # noqa: F811
    response = save(env, list(steps))
    assert response.status_code == 201, response.text
    session_id, token = guided(env, response.json())
    begin_steps(env, session_id, token)
    assert state(env, session_id)["phase"] == "stimuli"
    return session_id, token


def act(env, token, action, expression=None):  # noqa: F811
    body = {"action": action, **({"expression": expression} if expression else {})}
    return env.client.post(f"/participant-view/{token}/game", json=body)


def round_info(env, session_id):  # noqa: F811
    return state(env, session_id)["game"]


def wrong(info):
    return next(item for item in info["options"] if item != info["target_expression"]
                and item not in info["tried"] and item != info["removed"])


def results(env, session_id):  # noqa: F811
    return env.guided.repository.list_game_attempts(session_id)


# --- Dominio y armado del protocolo ------------------------------------------------------


def test_un_juego_valida_rondas_opciones_e_imagenes():
    item = ProtocolStep.matching_game(3, 2, 20)
    assert item.kind is StepKind.GAME and item.is_game and item.is_timed and not item.uses_camera
    assert item.seconds_limit == 60 and item.game_stimulus_ids == ()
    for values in ({"rounds": 1}, {"rounds": 7}, {"option_count": 1}, {"option_count": 5},
                   {"game_stimulus_ids": ("a", "b", "c", "d")}, {"game_type": "memoria"}):
        with pytest.raises((ValueError, TypeError)):
            ProtocolStep(None, 20, 0, kind=StepKind.GAME, **{"game_type": "matching", "rounds": 3,
                                                               "option_count": 2, **values})
    with pytest.raises(ValueError):
        ProtocolStep("img-1", 20, 0, kind=StepKind.GAME, game_type="matching", rounds=3, option_count=2)
    with pytest.raises(ValueError):
        ProtocolStep("img-1", 20, 0, rounds=3)                       # solo un juego tiene rondas


def test_el_resultado_solo_guarda_contadores():
    assert set(GameResult.__dataclass_fields__) == {
        "id", "session_id", "step_index", "game_type", "outcome", "started_at", "ended_at", "rounds_total",
        "rounds_done", "matched", "first_try", "help_used", "by_conductor", "attempt"}


def test_el_servidor_elige_una_imagen_por_ronda_de_emociones_distintas(env):  # noqa: F811
    images = bank(env)
    response = save(env, [game()])
    assert response.status_code == 201, response.text
    [saved] = response.json()["steps"]
    assert saved["kind"] == "game" and saved["rounds"] == 3 and saved["option_count"] == 2
    assert sorted(saved["game_stimulus_ids"]) == sorted(item["id"] for item in images)
    assert response.json()["uses_camera"] is False
    # Al editar se conservan las que sirven y se reemplaza la que no existe.
    kept = saved["game_stimulus_ids"][:2]
    edited = env.client.put(f"/protocols/{response.json()['id']}", headers=headers(env, env.user_1), json={
        "name": "Emparejar", "description": "", "for_children": False,
        "steps": [game(ids=[*kept, "no-existe"])]})
    assert edited.status_code == 200, edited.text
    ids = edited.json()["steps"][0]["game_stimulus_ids"]
    assert ids[:2] == kept and len(set(ids)) == 3


def test_sin_imagenes_suficientes_el_protocolo_no_se_guarda(env):  # noqa: F811
    bank(env, ("happiness", "sadness"))
    response = save(env, [game(rounds=3)])
    assert response.status_code == 422 and "baja las rondas" in response.json()["detail"]
    assert save(env, [game(rounds=2)]).status_code == 201


# --- Sesión ---------------------------------------------------------------------------------


def test_la_persona_juega_con_ayuda_reintento_y_explicacion(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2, options=3))
    shown = view(env, token).json()
    block = shown["game"]
    assert block["question"] == GAME_QUESTION and block["number"] == 1 and block["total"] == 2
    assert block["state"] == "playing" and block["answer"] is None and block["can_help"] is True
    assert len(block["options"]) == 3 and all(item["available"] for item in block["options"])
    # Sin cámara y con la imagen de la ronda.
    assert shown["capture_frames"] is False and shown.get("uses_camera") is False
    assert env.client.get(f"/participant-view/{token}/stimulus").status_code == 200
    assessed = env.frames_assessed
    frame(env, token)
    assert env.frames_assessed == assessed
    assert "target_expression" not in str(shown) and "matched" not in str(shown)

    info = round_info(env, session_id)
    first_image = info["stimulus_id"]
    assert act(env, token, "next").status_code == 409                  # la ronda no terminó
    assert act(env, token, "answer", "contempt").status_code == 422     # no se muestra
    miss = wrong(info)
    assert act(env, token, "answer", miss).json() == {"received": True}
    block = view(env, token).json()["game"]
    assert block["state"] == "retry" and block["message"] == GAME_RETRY
    assert [item["available"] for item in block["options"] if item["key"] == miss] == [False]
    assert act(env, token, "answer", miss).status_code == 422          # ya la eligió
    assert act(env, token, "help").status_code == 200
    block = view(env, token).json()["game"]
    assert block["can_help"] is False
    assert act(env, token, "answer", wrong(round_info(env, session_id))).status_code == 200
    block = view(env, token).json()["game"]
    target = info["target_expression"]
    assert block["state"] == "shown" and block["answer"] == target and block["message"].endswith(".")
    assert act(env, token, "next").status_code == 200

    info = round_info(env, session_id)
    assert info["round"] == 2 and info["stimulus_id"] != first_image
    assert act(env, token, "answer", info["target_expression"]).status_code == 200
    block = view(env, token).json()["game"]
    assert block["state"] == "matched" and block["message"].startswith("Lo encontraste: ")
    assert block["last_round"] is True
    assert act(env, token, "next").status_code == 200
    assert view(env, token).json()["game"]["state"] == "finished"
    [item] = results(env, session_id)
    assert item.outcome is GameOutcome.COMPLETED
    assert (item.rounds_total, item.rounds_done, item.matched, item.first_try, item.help_used,
            item.by_conductor) == (2, 2, 1, 1, 1, 0)
    assert act(env, token, "help").status_code == 409                  # ya terminó
    wait(env, 2.1)
    assert state(env, session_id)["phase"] == "finished"


def test_la_ayuda_quita_una_opcion_que_no_es(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2, options=4))
    act(env, token, "help")
    info = round_info(env, session_id)
    assert info["removed"] is not None and info["removed"] != info["target_expression"]
    options = view(env, token).json()["game"]["options"]
    assert sum(1 for item in options if item["available"]) == 3
    assert act(env, token, "answer", info["removed"]).status_code == 422



def test_tras_pedir_ayuda_no_se_le_vuelve_a_ofrecer(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2, options=3))
    assert act(env, token, "help").status_code == 200
    assert act(env, token, "answer", wrong(round_info(env, session_id))).status_code == 200
    block = view(env, token).json()["game"]
    assert block["state"] == "retry" and block["message"] == GAME_RETRY_HELPED and block["can_help"] is False

def test_quien_conduce_registra_la_emocion_y_pasa_de_ronda(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2))
    info = round_info(env, session_id)
    assert post(env, session_id, "game", {"action": "answer", "expression": info["target_expression"]}
                ).status_code == 200
    assert post(env, session_id, "game", {"action": "next"}).status_code == 200
    assert post(env, session_id, "game", {"action": "next"}, user=env.user_2).status_code in (403, 404)
    info = round_info(env, session_id)
    act(env, token, "answer", info["target_expression"])
    post(env, session_id, "game", {"action": "next"})
    [item] = results(env, session_id)
    assert (item.matched, item.first_try, item.by_conductor) == (2, 2, 1)


def test_al_vencer_el_tiempo_se_guardan_las_rondas_jugadas(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2, seconds=5), game(rounds=2))
    act(env, token, "answer", round_info(env, session_id)["target_expression"])
    act(env, token, "next")
    wait(env, 10.5)                                                    # 2 rondas × 5 s
    block = view(env, token).json()["game"]
    assert block["state"] == "ended" and block["message"] == "Terminó el tiempo del juego."
    [item] = results(env, session_id)
    assert item.outcome is GameOutcome.TIMED_OUT and (item.rounds_done, item.matched) == (1, 1)
    wait(env, 2)
    assert state(env, session_id)["step_index"] == 1


def test_repetir_el_juego_empieza_de_nuevo_y_guarda_otro_intento(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2))
    for _ in range(2):
        act(env, token, "answer", round_info(env, session_id)["target_expression"])
        act(env, token, "next")
    assert state(env, session_id)["can_repeat"] is True
    first_round = view(env, token).json()["game"]["round"]
    assert post(env, session_id, "repeat").status_code == 200
    block = view(env, token).json()["game"]
    assert block["state"] == "playing" and block["number"] == 1 and block["round"] != first_round
    act(env, token, "help")
    post(env, session_id, "skip")
    assert [(item.attempt, item.outcome, item.help_used) for item in results(env, session_id)] == [
        (1, GameOutcome.COMPLETED, 0), (2, GameOutcome.SKIPPED, 1)]
    summary = state(env, session_id)
    assert [item["outcome"] for item in summary["game_results"]] == ["completed"]
    assert [(item["step_kind"], item["attempt"]) for item in summary["repeated_attempts"]] == [("game", 2)]


def test_detener_durante_el_juego_lo_registra(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2))
    assert env.client.post(f"/participant-view/{token}/stop").json() == {"stopped": True}
    [item] = results(env, session_id)
    assert item.outcome is GameOutcome.STOPPED and item.rounds_done == 0


# --- Métricas, línea de tiempo y eliminación -------------------------------------------------


def test_las_metricas_describen_las_rondas_sin_puntaje(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2, options=3))
    info = round_info(env, session_id)
    act(env, token, "help")
    act(env, token, "answer", info["target_expression"])
    act(env, token, "next")
    act(env, token, "answer", wrong(round_info(env, session_id)))
    act(env, token, "answer", round_info(env, session_id)["target_expression"])
    act(env, token, "next")
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    block = metrics["game"]
    assert block["notice"] == GAME_NOTICE
    assert block["totals"]["sentence"] == "Jugó 2 de 2 rondas. Emparejó 2 imágenes, 1 a la primera; usó la ayuda 1 vez."
    assert block["totals"]["completed"] == 1 and block["exercises"][0]["rounds"] == 2
    assert "score" not in str(block) and "puntaje" not in str(block)
    assert metrics["recognition"] is None and metrics["emotional"] == []
    timeline = env.client.get(f"/sessions/{session_id}/timeline", headers=headers(env, env.user_1)).json()
    [lane] = [item for item in timeline["lanes"]["stimuli"] if item["kind"] == "game"]
    assert lane["outcome"] == "completed" and lane["sentence"].startswith("Jugó 2 de 2 rondas")


def test_eliminar_la_sesion_borra_los_resultados_del_juego(env):  # noqa: F811
    bank(env)
    session_id, token = start(env, game(rounds=2))
    post(env, session_id, "stop", {"reason": "conductor"})
    response = env.client.post(f"/sessions/{session_id}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 200, response.text
    assert response.json()["counts"]["game_results"] == 1
    assert results(env, session_id) == ()


def _migration():
    spec = importlib.util.spec_from_file_location("migration_20261106_41", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, name: str) -> None:  # noqa: F811
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), name)()


def test_la_migracion_41_sigue_a_los_dibujos():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261106_41", "20261106_40")


def test_la_migracion_41_vuelve_atras_y_otra_vez_adelante(engine):  # noqa: F811
    assert "game_results" in inspect(engine).get_table_names()
    _run(engine, "downgrade")
    assert "game_results" not in inspect(engine).get_table_names()
    assert "rounds" not in {item["name"] for item in inspect(engine).get_columns("protocol_steps")}
    _run(engine, "upgrade")
    assert "game_results" in inspect(engine).get_table_names()
    assert "game_progress" in {item["name"] for item in inspect(engine).get_columns("guided_runs")}
    checks = {item["name"]: item["sqltext"] for item in inspect(engine).get_check_constraints("protocol_steps")}
    assert "'game'" in checks["ck_protocol_steps_kind"]



def test_la_base_guarda_un_juego_junto_a_otros_pasos(factory):  # noqa: F811
    """None en las columnas JSON del juego se guarda como NULL de SQL: si no, las
    restricciones rechazan cualquier paso que no sea un juego."""
    repository = PostgresProtocolRepository(factory)
    repository.add(replace(protocol(), id="p-juego", family_id="f-juego",
                           steps=(*protocol().steps, ProtocolStep.matching_game(2, 2, 30, ("s1",)))))
    stored = repository.get("p-juego")
    assert [step.kind for step in stored.steps] == [StepKind.STIMULUS, StepKind.PRACTICE, StepKind.PRACTICE,
                                                     StepKind.GAME]
    assert stored.steps[-1].game_stimulus_ids == ("s1",) and stored.steps[0].game_stimulus_ids == ()
