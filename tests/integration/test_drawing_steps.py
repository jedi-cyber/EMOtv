"""Pasos de dibujo en la sesión guiada (bloque 4, subtarea 4a): armado del
protocolo, emoción señalada por la persona o por quien conduce, tiempo vencido,
repetir, saltar, detener, métricas, línea de tiempo, eliminación y migración.
El dibujo nunca llega al servidor: solo la emoción elegida y los tiempos.
(SQLite en memoria, reloj falso y analizador falso; sin modelos ni imágenes.)"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from emotv.domain.guided_session import (
    DRAWING_INSTRUCTION,
    DRAWING_NOTICE,
    DRAWING_OPTIONS,
    DRAWING_QUESTION,
    DrawingResult,
    RecognitionAnswerer,
    RecognitionOutcome,
)
from emotv.domain.protocol import ProtocolStep, StepKind
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
from tests.integration.test_practice_persistence import engine  # noqa: F401
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261106_40_drawing_steps.py"


def drawing(exposure=30):
    return {"kind": "drawing", "exposure_seconds": exposure}


def start(env, *steps):  # noqa: F811
    session_id, token = guided(env, protocol(env, list(steps)))
    begin_steps(env, session_id, token)
    current = state(env, session_id)
    assert current["phase"] == "stimuli" and current["step_index"] == 0
    return session_id, token


def answer(env, token, expression):  # noqa: F811
    return env.client.post(f"/participant-view/{token}/answer", json={"expression": expression})


def results(env, session_id):  # noqa: F811
    return env.guided.repository.list_drawing_attempts(session_id)


# --- Dominio y armado del protocolo ------------------------------------------------------


def test_un_dibujo_no_lleva_imagen_expresion_ni_opciones():
    item = ProtocolStep.drawing(60)
    assert item.kind is StepKind.DRAWING and item.is_drawing and item.is_timed and not item.uses_camera
    for extra in ({"stimulus_id": "img-1"}, {"target_expression": "happiness"}, {"option_count": 3},
                  {"hold_seconds": 2}):
        values = {"stimulus_id": None, **extra}
        with pytest.raises(ValueError):
            ProtocolStep(values.pop("stimulus_id"), 60, 0, kind=StepKind.DRAWING, **values)
    with pytest.raises(ValueError):
        ProtocolStep(None, 60, 5, kind=StepKind.DRAWING)


def test_el_resultado_solo_guarda_la_emocion_y_los_tiempos():
    fields = set(DrawingResult.__dataclass_fields__)
    assert fields == {"id", "session_id", "step_index", "outcome", "started_at", "ended_at", "chosen_expression",
                      "seconds_to_answer", "answered_by", "attempt"}


def test_el_protocolo_guarda_el_paso_de_dibujo(env):  # noqa: F811
    item = protocol(env, [drawing(45)])
    [saved] = item["steps"]
    assert saved["kind"] == "drawing" and saved["stimulus_id"] is None
    assert saved["exposure_seconds"] == 45 and saved["target_expression"] is None
    emotional, _ = stimuli(env)
    response = env.client.post("/protocols", headers=headers(env, env.user_1), json={
        "name": "Dibujo", "description": "", "for_children": False,
        "steps": [{**drawing(), "stimulus_id": emotional["id"]}]})
    assert response.status_code == 422


# --- Sesión ---------------------------------------------------------------------------------


def test_la_persona_senala_la_emocion_y_el_paso_avanza_sin_camara(env):  # noqa: F811
    session_id, token = start(env, drawing())
    shown = view(env, token).json()
    block = shown["drawing"]
    assert block["instruction"] == DRAWING_INSTRUCTION and block["question"] == DRAWING_QUESTION
    assert [option["key"] for option in block["options"]] == list(DRAWING_OPTIONS)
    assert block["finished"] is False and block["chosen"] is None and block["message"] is None
    # Sin imagen, sin cámara y sin los bloques de otros pasos.
    assert shown["stimulus"] is None and shown["capture_frames"] is False
    assert "practice" not in shown and "recognition" not in shown and shown.get("uses_camera") is False
    assessed = env.frames_assessed
    frame(env, token)
    assert env.frames_assessed == assessed

    wait(env, 12)
    assert answer(env, token, "contempt").status_code == 422          # no se ofrece
    assert answer(env, token, "happiness").json() == {"received": True}
    assert answer(env, token, "sadness").status_code == 409           # ya respondió
    block = view(env, token).json()["drawing"]
    assert block["finished"] is True and block["chosen"] == "happiness"
    assert block["message"] == "Dibujaste alegría."
    [item] = results(env, session_id)
    assert item.outcome is RecognitionOutcome.ANSWERED and item.chosen_expression == "happiness"
    assert item.seconds_to_answer == 12.0 and item.answered_by is RecognitionAnswerer.PARTICIPANT
    conductor = state(env, session_id)
    assert conductor["drawing"]["chosen_expression"] == "happiness"
    assert conductor["drawing_results"] == [{"step_index": 0, "outcome": "answered",
                                             "chosen_expression": "happiness", "seconds_to_answer": 12.0,
                                             "answered_by": "participant"}]
    assert conductor["captures"] == [] and conductor["recognition_results"] == []
    wait(env, 2.1)
    assert state(env, session_id)["phase"] == "finished"


def test_quien_conduce_registra_la_emocion_que_la_persona_senalo(env):  # noqa: F811
    session_id, token = start(env, drawing())
    wait(env, 4)
    assert post(env, session_id, "recognition", {"expression": "neutral"}).status_code == 200
    [item] = results(env, session_id)
    assert item.answered_by is RecognitionAnswerer.CONDUCTOR and item.chosen_expression == "neutral"
    assert view(env, token).json()["drawing"]["message"] == "Dibujaste una cara tranquila."
    assert post(env, session_id, "recognition", {"expression": "neutral"}, user=env.user_2).status_code in (403, 404)


def test_al_vencer_el_tiempo_se_registra_sin_respuesta(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = start(env, drawing(5), drawing(10))
    wait(env, 5.5)
    block = view(env, token).json()["drawing"]
    assert block["finished"] is True and block["chosen"] is None and block["message"] is None
    assert answer(env, token, "happiness").status_code == 409
    [item] = results(env, session_id)
    assert item.outcome is RecognitionOutcome.TIMED_OUT and item.chosen_expression is None
    wait(env, 2)
    assert state(env, session_id)["step_index"] == 1


def test_repetir_un_dibujo_guarda_otro_intento_y_cambia_la_ronda(env):  # noqa: F811
    session_id, token = start(env, drawing())
    first_round = view(env, token).json()["drawing"]["round"]
    wait(env, 3)
    answer(env, token, "anger")
    assert state(env, session_id)["can_repeat"] is True
    assert post(env, session_id, "repeat").status_code == 200
    block = view(env, token).json()["drawing"]
    assert block["round"] != first_round and block["finished"] is False
    wait(env, 2)
    answer(env, token, "fear")
    assert [(item.attempt, item.chosen_expression) for item in results(env, session_id)] == [(1, "anger"),
                                                                                              (2, "fear")]
    summary = state(env, session_id)
    assert [item["chosen_expression"] for item in summary["drawing_results"]] == ["anger"]
    assert [(item["step_kind"], item["attempt"], item["chosen_expression"])
            for item in summary["repeated_attempts"]] == [("drawing", 2, "fear")]


def test_saltar_o_detener_un_dibujo_lo_registra(env):  # noqa: F811
    session_id, token = start(env, drawing(), drawing())
    wait(env, 1)
    assert post(env, session_id, "skip").status_code == 200
    wait(env, 1)
    assert env.client.post(f"/participant-view/{token}/stop").json() == {"stopped": True}
    assert [item.outcome for item in results(env, session_id)] == [RecognitionOutcome.SKIPPED,
                                                                    RecognitionOutcome.STOPPED]


# --- Métricas, línea de tiempo y eliminación -------------------------------------------------


def test_las_metricas_describen_la_emocion_senalada_sin_mezclarla(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = start(env, drawing(), drawing(4), step(emotional))
    wait(env, 2)
    answer(env, token, "surprise")
    wait(env, 2.1)
    assert state(env, session_id)["step_index"] == 1
    wait(env, 6.5)                                                     # el segundo vence
    assert state(env, session_id)["step_index"] == 2
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    block = metrics["drawing"]
    assert block["notice"] == DRAWING_NOTICE
    assert block["totals"]["sentence"] == "Señaló una emoción en 1 de 2 dibujos."
    assert block["totals"]["timed_out"] == 1
    assert [row["chosen_expression"] for row in block["exercises"]] == ["surprise", None]
    assert metrics["recognition"] is None and metrics["practice"] is None
    assert [row["step_index"] for row in metrics["emotional"]] == [2]
    timeline = env.client.get(f"/sessions/{session_id}/timeline", headers=headers(env, env.user_1)).json()
    lane = [item for item in timeline["lanes"]["stimuli"] if item["kind"] == "drawing"]
    assert [(item["outcome"], item["chosen_expression"]) for item in lane] == [("answered", "surprise"),
                                                                                ("timed_out", None)]


def test_eliminar_la_sesion_borra_los_dibujos_registrados(env):  # noqa: F811
    session_id, token = start(env, drawing())
    answer(env, token, "happiness")
    post(env, session_id, "stop", {"reason": "conductor"})
    response = env.client.post(f"/sessions/{session_id}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 200, response.text
    assert response.json()["counts"]["drawing_results"] == 1
    assert results(env, session_id) == ()


def _migration():
    spec = importlib.util.spec_from_file_location("migration_20261106_40", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, name: str) -> None:  # noqa: F811
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), name)()


def test_la_migracion_40_sigue_a_los_intentos():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261106_40", "20261106_39")


def test_la_migracion_40_vuelve_atras_y_otra_vez_adelante(engine):  # noqa: F811
    assert "drawing_results" in inspect(engine).get_table_names()
    _run(engine, "downgrade")
    assert "drawing_results" not in inspect(engine).get_table_names()
    _run(engine, "upgrade")
    assert "drawing_results" in inspect(engine).get_table_names()
    checks = {item["name"]: item["sqltext"] for item in inspect(engine).get_check_constraints("protocol_steps")}
    assert "'drawing'" in checks["ck_protocol_steps_kind"]
