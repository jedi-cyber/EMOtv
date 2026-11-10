"""Modo accesible de un protocolo: se guarda con el protocolo, llega a la
pantalla de la persona y alarga la pausa tras cada reconocimiento o ejercicio.
Incluye la migración 20261102_33 (SQLite en memoria, reloj falso; sin modelos)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from emotv.domain.protocol import Protocol, ProtocolKind
from emotv.infrastructure.persistence.postgres_practice_repositories import PostgresProtocolRepository
from tests.integration.test_guided_sessions import begin_steps, guided, state, view, wait
from tests.integration.test_practice_persistence import T0, engine, factory  # noqa: F401
from tests.integration.test_practice_persistence import protocol as stored_protocol
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_recognition_sessions import answer, recognition, sad_stimulus

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261102_33_accessible_protocols.py"


def accessible_protocol(env, steps, accessible=True):  # noqa: F811
    body = {"name": "Accesible", "description": "", "for_children": False, "steps": steps, "accessible": accessible}
    response = env.client.post("/protocols", headers=headers(env, env.user_1), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def start(env, item):  # noqa: F811
    session_id, token = guided(env, item)
    begin_steps(env, session_id, token)
    return session_id, token


def test_el_protocolo_guarda_el_modo_accesible_y_se_puede_quitar(env):  # noqa: F811
    sad = sad_stimulus(env)
    item = accessible_protocol(env, [recognition(sad)])
    assert item["accessible"] is True
    body = {"name": item["name"], "description": "", "for_children": False, "steps": item["steps"]}
    edited = env.client.put(f"/protocols/{item['id']}", headers=headers(env, env.user_1), json=body)
    # Sin indicarlo, un protocolo no es accesible.
    assert edited.status_code == 200 and edited.json()["accessible"] is False


def test_la_pantalla_de_la_persona_y_quien_conduce_saben_que_es_accesible(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, accessible_protocol(env, [recognition(sad)]))
    assert view(env, token).json()["accessible"] is True
    assert state(env, session_id)["accessible"] is True


def test_sin_modo_accesible_la_pantalla_no_cambia(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, accessible_protocol(env, [recognition(sad)], accessible=False))
    # Sin modo accesible, la pantalla de la persona recibe lo mismo que antes.
    assert "accessible" not in view(env, token).json()
    assert state(env, session_id)["accessible"] is False


@pytest.mark.parametrize("accessible,still_paused_at", [(False, None), (True, 3)])
def test_la_pausa_tras_responder_es_el_doble_en_modo_accesible(env, accessible, still_paused_at):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, accessible_protocol(env, [recognition(sad), recognition(sad)], accessible))
    assert answer(env, token, "sadness").json() == {"received": True}
    # La pausa normal es de 2 s; en modo accesible, de 4 s.
    wait(env, 2.1)
    assert state(env, session_id)["step_index"] == (0 if accessible else 1)
    if still_paused_at:
        wait(env, 2)
        assert state(env, session_id)["step_index"] == 1


def test_un_examen_no_tiene_modo_accesible():
    with pytest.raises(ValueError, match="modo accesible"):
        Protocol(id="e1", family_id="e1", version=1, owner_user_id="u1", name="Examen", description="",
                 for_children=False, created_at=T0, kind=ProtocolKind.EXAM, accessible=True)


def test_ida_y_vuelta(factory):  # noqa: F811
    item = stored_protocol(accessible=True)
    PostgresProtocolRepository(factory).replace(item)
    assert PostgresProtocolRepository(factory).get("p1") == item


def _run(engine, step: str) -> None:  # noqa: F811
    spec = importlib.util.spec_from_file_location("migration_20261102_33", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ("20261102_33", "20261102_32")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()


def test_migracion_downgrade_y_upgrade(engine, factory):  # noqa: F811
    PostgresProtocolRepository(factory).replace(stored_protocol())
    _run(engine, "downgrade")
    assert "accessible" not in {column["name"] for column in inspect(engine).get_columns("protocols")}
    _run(engine, "upgrade")
    # Los protocolos existentes quedan sin modo accesible.
    assert PostgresProtocolRepository(factory).get("p1").accessible is False
    test_ida_y_vuelta(factory)
