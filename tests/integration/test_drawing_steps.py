"""Pasos de dibujo en la sesión guiada (bloque 4, subtarea 4a): armado del
protocolo, «Terminé» de la persona o de quien conduce (sin preguntar qué emoción
quiso dibujar, desde 20261124_48), tiempo vencido, repetir, saltar, detener,
métricas, línea de tiempo, eliminación y migraciones. El dibujo nunca llega al
servidor: solo si terminó y los tiempos.
(SQLite en memoria, reloj falso y analizador falso; sin modelos ni imágenes.)"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from emotv.domain.guided_session import (
    DRAWING_FINISHED,
    DRAWING_INSTRUCTION,
    DRAWING_NOTICE,
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

VERSIONS = Path(__file__).resolve().parents[2] / "migrations" / "versions"
MIGRATION = VERSIONS / "20261106_40_drawing_steps.py"
WITHOUT_QUESTION = VERSIONS / "20261124_48_drawing_without_question.py"


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


def done(env, token):  # noqa: F811
    return env.client.post(f"/participant-view/{token}/drawing-done")


def results(env, session_id):  # noqa: F811
    return env.guided.repository.list_drawing_attempts(session_id)


# --- Dominio y armado del protocolo ------------------------------------------------------


def test_un_dibujo_no_lleva_expresion_ni_opciones():
    item = ProtocolStep.drawing(60)
    assert item.kind is StepKind.DRAWING and item.is_drawing and item.is_timed and not item.uses_camera
    # Puede llevar una imagen para mirar antes de dibujar; sigue sin usar la cámara.
    with_image = ProtocolStep.drawing(60, stimulus_id="img-1")
    assert with_image.stimulus_id == "img-1" and not with_image.uses_camera
    for extra in ({"target_expression": "happiness"}, {"option_count": 3}, {"hold_seconds": 2}):
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
    # Con una imagen para mirar antes de dibujar (desde 20261124_46).
    assert response.status_code == 201, response.text
    assert response.json()["steps"][0]["stimulus_id"] == emotional["id"]


# --- Sesión ---------------------------------------------------------------------------------


def test_la_persona_termina_el_dibujo_sin_elegir_emocion_y_el_paso_avanza_sin_camara(env):  # noqa: F811
    session_id, token = start(env, drawing())
    shown = view(env, token).json()
    block = shown["drawing"]
    # No se pregunta qué emoción quiso dibujar.
    assert block["instruction"] == DRAWING_INSTRUCTION and block["question"] is None and block["options"] == []
    assert block["finished"] is False and block["chosen"] is None and block["message"] is None
    # Sin imagen, sin cámara y sin los bloques de otros pasos.
    assert shown["stimulus"] is None and shown["capture_frames"] is False
    assert "practice" not in shown and "recognition" not in shown and shown.get("uses_camera") is False
    assessed = env.frames_assessed
    frame(env, token)
    assert env.frames_assessed == assessed

    wait(env, 12)
    assert done(env, token).json() == {"received": True}
    assert done(env, token).status_code == 409                       # ya terminó
    block = view(env, token).json()["drawing"]
    assert block["finished"] is True and block["chosen"] is None and block["message"] == DRAWING_FINISHED
    [item] = results(env, session_id)
    assert item.outcome is RecognitionOutcome.ANSWERED and item.chosen_expression is None
    assert item.seconds_to_answer == 12.0 and item.answered_by is RecognitionAnswerer.PARTICIPANT
    conductor = state(env, session_id)
    assert conductor["drawing"]["outcome"] == "answered" and conductor["drawing"]["chosen_expression"] is None
    assert conductor["drawing_results"] == [{"step_index": 0, "outcome": "answered",
                                             "chosen_expression": None, "seconds_to_answer": 12.0,
                                             "answered_by": "participant"}]
    assert conductor["captures"] == [] and conductor["recognition_results"] == []
    wait(env, 2.1)
    assert state(env, session_id)["phase"] == "finished"


def test_un_aplicativo_anterior_que_envia_una_emocion_termina_el_dibujo_sin_guardarla(env):  # noqa: F811
    session_id, token = start(env, drawing())
    wait(env, 3)
    assert answer(env, token, "happiness").json() == {"received": True}
    [item] = results(env, session_id)
    assert item.outcome is RecognitionOutcome.ANSWERED and item.chosen_expression is None


def test_quien_conduce_marca_que_termino_de_dibujar(env):  # noqa: F811
    session_id, token = start(env, drawing())
    wait(env, 4)
    assert post(env, session_id, "drawing-done", user=env.user_2).status_code in (403, 404)
    assert post(env, session_id, "drawing-done").status_code == 200
    [item] = results(env, session_id)
    assert item.answered_by is RecognitionAnswerer.CONDUCTOR and item.chosen_expression is None
    assert view(env, token).json()["drawing"]["message"] == DRAWING_FINISHED
    assert post(env, session_id, "drawing-done").status_code == 409


def test_terminado_solo_existe_en_un_paso_de_dibujo(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = start(env, step(emotional))
    assert done(env, token).status_code == 409
    assert post(env, session_id, "drawing-done").status_code == 409


def test_al_vencer_el_tiempo_se_registra_sin_terminar(env):  # noqa: F811
    session_id, token = start(env, drawing(5), drawing(10))
    wait(env, 5.5)
    block = view(env, token).json()["drawing"]
    assert block["finished"] is True and block["chosen"] is None and block["message"] is None
    assert done(env, token).status_code == 409
    [item] = results(env, session_id)
    assert item.outcome is RecognitionOutcome.TIMED_OUT and item.chosen_expression is None
    wait(env, 2)
    assert state(env, session_id)["step_index"] == 1


def test_repetir_un_dibujo_guarda_otro_intento_y_cambia_la_ronda(env):  # noqa: F811
    session_id, token = start(env, drawing())
    first_round = view(env, token).json()["drawing"]["round"]
    wait(env, 3)
    done(env, token)
    assert state(env, session_id)["can_repeat"] is True
    assert post(env, session_id, "repeat").status_code == 200
    block = view(env, token).json()["drawing"]
    assert block["round"] != first_round and block["finished"] is False
    wait(env, 2)
    done(env, token)
    assert [(item.attempt, item.seconds_to_answer) for item in results(env, session_id)] == [(1, 3.0), (2, 2.0)]
    summary = state(env, session_id)
    assert [item["outcome"] for item in summary["drawing_results"]] == ["answered"]
    assert [(item["step_kind"], item["attempt"]) for item in summary["repeated_attempts"]] == [("drawing", 2)]


def test_saltar_o_detener_un_dibujo_lo_registra(env):  # noqa: F811
    session_id, token = start(env, drawing(), drawing())
    wait(env, 1)
    assert post(env, session_id, "skip").status_code == 200
    wait(env, 1)
    assert env.client.post(f"/participant-view/{token}/stop").json() == {"stopped": True}
    assert [item.outcome for item in results(env, session_id)] == [RecognitionOutcome.SKIPPED,
                                                                    RecognitionOutcome.STOPPED]


# --- Métricas, línea de tiempo y eliminación -------------------------------------------------


def test_las_metricas_describen_si_termino_sin_mezclarlo(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = start(env, drawing(), drawing(4), step(emotional))
    wait(env, 2)
    done(env, token)
    wait(env, 2.1)
    assert state(env, session_id)["step_index"] == 1
    wait(env, 6.5)                                                     # el segundo vence
    assert state(env, session_id)["step_index"] == 2
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    block = metrics["drawing"]
    assert block["notice"] == DRAWING_NOTICE
    assert block["totals"]["sentence"] == "Terminó 1 de 2 dibujos."
    assert block["totals"]["timed_out"] == 1
    assert [(row["outcome"], row["chosen_expression"]) for row in block["exercises"]] == [("answered", None),
                                                                                          ("timed_out", None)]
    assert metrics["recognition"] is None and metrics["practice"] is None
    assert [row["step_index"] for row in metrics["emotional"]] == [2]
    timeline = env.client.get(f"/sessions/{session_id}/timeline", headers=headers(env, env.user_1)).json()
    lane = [item for item in timeline["lanes"]["stimuli"] if item["kind"] == "drawing"]
    assert [(item["outcome"], item["chosen_expression"]) for item in lane] == [("answered", None),
                                                                                ("timed_out", None)]


def test_eliminar_la_sesion_borra_los_dibujos_registrados(env):  # noqa: F811
    session_id, token = start(env, drawing())
    done(env, token)
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


def test_una_sesion_anterior_conserva_la_emocion_que_se_senalo(env):  # noqa: F811
    """Antes de 20261124_48 se preguntaba qué emoción quiso dibujar: se sigue leyendo."""
    session_id, token = start(env, drawing())
    run = env.guided.repository.get_run(session_id)
    env.guided.repository.save_drawing_result(DrawingResult(
        id="anterior", session_id=session_id, step_index=0, outcome=RecognitionOutcome.ANSWERED,
        started_at=run.step_started_at, ended_at=run.step_started_at, chosen_expression="happiness",
        seconds_to_answer=0.0, answered_by=RecognitionAnswerer.PARTICIPANT))
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    assert metrics["drawing"]["exercises"][0]["chosen_expression"] == "happiness"
    assert metrics["educational"]["drawing"]["sentence"] == "Terminó 1 de 1 dibujo; señaló alegría (1)."


def test_solo_un_dibujo_terminado_lleva_segundos_y_quien_lo_termino():
    from datetime import UTC, datetime
    now = datetime(2026, 11, 24, tzinfo=UTC)
    base = {"id": "d", "session_id": "s", "step_index": 0, "started_at": now, "ended_at": now}
    DrawingResult(**base, outcome="answered", seconds_to_answer=1.0, answered_by="participant")
    with pytest.raises(ValueError):
        DrawingResult(**base, outcome="answered")
    with pytest.raises(ValueError):
        DrawingResult(**base, outcome="timed_out", chosen_expression="happiness")


def _without_question(engine, name: str) -> None:  # noqa: F811
    spec = importlib.util.spec_from_file_location("migration_20261124_48", WITHOUT_QUESTION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ("20261124_48", "20261124_47")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, name)()


def test_la_migracion_48_vuelve_atras_y_otra_vez_adelante(engine):  # noqa: F811
    def check():
        return {item["name"]: item["sqltext"] for item in inspect(engine).get_check_constraints("drawing_results")}

    assert "chosen_expression IS NULL" in check()["ck_drawing_results_answered"]
    _without_question(engine, "downgrade")
    assert "(chosen_expression IS NOT NULL)" in check()["ck_drawing_results_answered"]
    _without_question(engine, "upgrade")
    assert "OR chosen_expression IS NULL" in check()["ck_drawing_results_answered"]
