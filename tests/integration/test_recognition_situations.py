"""Situaciones en el paso «¿Qué emoción es?»: una historia corta junto a la
ilustración. Dominio, armado del protocolo, sesión guiada, persistencia y la
migración 20261102_32 (SQLite en memoria, reloj falso; sin modelos ni personas)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from emotv.domain.guided_session import RECOGNITION_QUESTION, SITUATION_QUESTION
from emotv.domain.protocol import MAX_SITUATION_CHARS, ProtocolStep
from emotv.infrastructure.persistence.models import ProtocolStepRecord
from emotv.infrastructure.persistence.postgres_practice_repositories import PostgresProtocolRepository
from tests.integration.test_guided_sessions import protocol, state, view
from tests.integration.test_practice_persistence import engine, factory  # noqa: F401
from tests.integration.test_practice_persistence import protocol as stored_protocol
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_recognition_sessions import answer, recognition, sad_stimulus, start

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261102_32_recognition_situations.py"
STORY = "A Lucía se le cayó su helado al piso."


def situation(stimulus, text=STORY, **fields):
    return {**recognition(stimulus, **fields), "situation": text}


# --- Dominio ------------------------------------------------------------------------------


def test_la_situacion_se_limpia_y_solo_va_en_un_reconocimiento():
    step = ProtocolStep.recognition("s1", 10, situation="  A Lucía   se le cayó\nsu helado ")
    assert step.situation == "A Lucía se le cayó su helado"
    assert ProtocolStep.recognition("s1", 10, situation="   ").situation is None
    with pytest.raises(ValueError, match="máximo"):
        ProtocolStep.recognition("s1", 10, situation="a" * (MAX_SITUATION_CHARS + 1))
    with pytest.raises(ValueError, match="Solo un paso"):
        ProtocolStep("s1", 10, 2, situation=STORY)
    with pytest.raises(ValueError, match="Solo un paso"):
        ProtocolStep(None, 10, 0, kind="practice", target_expression="happiness", hold_seconds=2, situation=STORY)


# --- Armado y sesión --------------------------------------------------------------------------


def test_el_protocolo_guarda_la_situacion_y_rechaza_identificadores(env):  # noqa: F811
    sad = sad_stimulus(env)
    [saved] = protocol(env, [situation(sad)])["steps"]
    assert saved["situation"] == STORY and saved["target_expression"] == "sadness"
    body = {"name": "Situaciones", "description": "", "for_children": False}
    for text in ("Lucía, DNI 12345678, perdió su helado", "Escribe a lucia@correo.com"):
        response = env.client.post("/protocols", headers=headers(env, env.user_1),
                                   json={**body, "steps": [situation(sad, text)]})
        assert response.status_code == 422 and "nombres inventados" in response.json()["detail"]
    response = env.client.post("/protocols", headers=headers(env, env.user_1),
                               json={**body, "steps": [situation(sad, "a" * (MAX_SITUATION_CHARS + 1))]})
    assert response.status_code == 422


def test_con_situacion_se_pregunta_por_la_cara_de_la_imagen(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, situation(sad), recognition(sad))
    block = view(env, token).json()["recognition"]
    assert block["question"] == SITUATION_QUESTION and block["situation"] == STORY
    conductor = state(env, session_id)
    assert conductor["recognition"]["situation"] == STORY and conductor["steps"][0]["situation"] == STORY
    assert block["question"] == "¿Qué emoción muestra la cara?" and block["note"] is None
    # Al terminar se lee la expresión de la imagen, no lo que alguien siente, y
    # que en una situación así cada persona puede sentir algo distinto.
    assert answer(env, token, "sadness").json() == {"received": True}
    block = view(env, token).json()["recognition"]
    assert block["message"] == "La cara de la imagen muestra tristeza."
    assert block["note"] == "En una situación así, cada persona puede sentir algo distinto."


def test_sin_situacion_la_pregunta_no_cambia(env):  # noqa: F811
    sad = sad_stimulus(env)
    _, token = start(env, recognition(sad))
    block = view(env, token).json()["recognition"]
    assert block["question"] == RECOGNITION_QUESTION and block["situation"] is None


# --- Persistencia y migración -------------------------------------------------------------


def test_situacion_ida_y_vuelta(factory):  # noqa: F811
    item = stored_protocol(steps=(*stored_protocol().steps, ProtocolStep.recognition("s1", 12, 3, "sadness", STORY)))
    PostgresProtocolRepository(factory).replace(item)
    found = PostgresProtocolRepository(factory).get("p1")
    assert found == item and found.steps[-1].situation == STORY


def test_la_base_rechaza_una_situacion_fuera_de_un_reconocimiento(factory):  # noqa: F811
    row = dict(id="x1", protocol_id="p1", position=9, stimulus_id="s1", exposure_seconds=10,
               capture_after_seconds=2, record_verbal_response=False, shown_before_analyzer=False,
               kind="stimulus", situation=STORY)
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.add(ProtocolStepRecord(**row))


def _run(engine, step: str) -> None:  # noqa: F811
    spec = importlib.util.spec_from_file_location("migration_20261102_32", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ("20261102_32", "20261102_31")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()


def test_migracion_downgrade_y_upgrade(engine, factory):  # noqa: F811
    _run(engine, "downgrade")
    assert "situation" not in {column["name"] for column in inspect(engine).get_columns("protocol_steps")}
    _run(engine, "upgrade")
    test_situacion_ida_y_vuelta(factory)
