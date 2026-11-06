"""Bloque 2b: apoyos configurables por protocolo. El modo accesible de antes es
un preajuste; sin límite de tiempo y la pausa «esperar a quien conduce» cambian
el ritmo, no lo que se registra. Incluye la migración 20261106_38 (SQLite en
memoria, reloj falso; sin modelos ni personas)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect, text

from emotv.domain.guided_session import PracticeOutcome, RecognitionOutcome
from emotv.domain.protocol import (ACCESSIBLE_PRESET, NO_SUPPORTS, PauseMode, Protocol, ProtocolKind, ProtocolStep,
                                   ProtocolSupports)
from emotv.infrastructure.persistence.postgres_practice_repositories import PostgresProtocolRepository
from tests.integration.test_guided_sessions import begin_steps, guided, post, state, view, wait
from tests.integration.test_practice_persistence import T0, engine, factory  # noqa: F401
from tests.integration.test_practice_persistence import protocol as stored_protocol
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_recognition_sessions import answer, recognition, results, sad_stimulus

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261106_38_protocol_supports.py"


def with_supports(env, steps, **supports):  # noqa: F811
    body = {"name": "Con apoyos", "description": "", "for_children": False, "steps": steps, "supports": supports}
    response = env.client.post("/protocols", headers=headers(env, env.user_1), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def start(env, item):  # noqa: F811
    session_id, token = guided(env, item)
    begin_steps(env, session_id, token)
    return session_id, token


# --- Dominio y API --------------------------------------------------------------------------


def test_el_modo_accesible_es_el_preajuste_de_siempre():
    common = dict(id="p", family_id="p", version=1, owner_user_id="u", name="P", description="",
                  for_children=True, created_at=T0, steps=(ProtocolStep.recognition("s1", 10),))
    assert Protocol(**common, accessible=True).supports == ACCESSIBLE_PRESET
    assert Protocol(**common).supports == NO_SUPPORTS and Protocol(**common).accessible is False
    # accessible indica si hay algún apoyo; los apoyos mandan.
    only_time = Protocol(**common, accessible=True, supports=ProtocolSupports(no_time_limit=True))
    assert only_time.accessible is True and only_time.supports.pictograms is False
    with pytest.raises(ValueError, match="apoyos"):
        Protocol(id="e", family_id="e", version=1, owner_user_id="u", name="E", description="", for_children=False,
                 created_at=T0, kind=ProtocolKind.EXAM, supports=ProtocolSupports(read_aloud=True))
    with pytest.raises(ValueError):
        ProtocolSupports(pause="forever")


def test_el_protocolo_guarda_cada_apoyo_y_el_preajuste_antiguo_sigue_valiendo(env):  # noqa: F811
    sad = sad_stimulus(env)
    item = with_supports(env, [recognition(sad)], read_aloud=True, no_time_limit=True, pause="wait")
    assert item["supports"] == {"pictograms": False, "large_controls": False, "read_aloud": True,
                                "no_time_limit": True, "pause": "wait"}
    assert item["accessible"] is True
    body = {"name": "Antiguo", "description": "", "for_children": False, "steps": item["steps"], "accessible": True}
    legacy = env.client.post("/protocols", headers=headers(env, env.user_1), json=body).json()
    assert legacy["supports"] == {"pictograms": True, "large_controls": True, "read_aloud": False,
                                  "no_time_limit": False, "pause": "long"}
    bad = env.client.post("/protocols", headers=headers(env, env.user_1),
                          json={**body, "supports": {"pause": "forever"}})
    assert bad.status_code == 422


# --- En la sesión -----------------------------------------------------------------------------


def test_sin_limite_de_tiempo_el_reconocimiento_espera_la_respuesta(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, with_supports(env, [recognition(sad, exposure=5), recognition(sad)],
                                                 no_time_limit=True))
    wait(env, 60)
    current = state(env, session_id)
    assert current["step_index"] == 0 and current["remaining_seconds"] is None
    screen = view(env, token).json()
    # Solo cambia el ritmo: la pantalla no recibe apoyos de presentación.
    assert screen["remaining_seconds"] is None and "supports" not in screen
    assert screen["recognition"]["message"] is None and results(env, session_id) == ()
    assert answer(env, token, "sadness").json() == {"received": True}
    [item] = results(env, session_id)
    assert item.outcome is RecognitionOutcome.ANSWERED and item.seconds_to_answer == pytest.approx(60, abs=0.5)
    wait(env, 2.1)
    assert state(env, session_id)["step_index"] == 1


def test_sin_limite_de_tiempo_la_practica_no_vence_y_se_puede_saltar(env):  # noqa: F811
    item = Protocol(id=str(uuid4()), family_id=str(uuid4()), version=1, owner_user_id=env.user_1.id,
                    name="Práctica", description="", for_children=False, created_at=env.clock.now,
                    steps=(ProtocolStep.practice("happiness", 2, 10), ProtocolStep.practice("surprise", 2, 10)),
                    supports=ProtocolSupports(no_time_limit=True))
    env.protocols.repository.add(item)
    session_id, token = start(env, {"id": item.id, "for_children": False})
    wait(env, 30)
    assert state(env, session_id)["step_index"] == 0
    assert view(env, token).json()["practice"]["achieved"] is False
    assert env.guided.repository.list_practice_results(session_id) == ()
    assert post(env, session_id, "skip").status_code == 200
    [result] = env.guided.repository.list_practice_results(session_id)
    assert result.outcome is PracticeOutcome.SKIPPED and state(env, session_id)["step_index"] == 1


def test_esperar_a_quien_conduce_hasta_que_pulse_seguir(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, with_supports(env, [recognition(sad), recognition(sad)], pause="wait"))
    assert post(env, session_id, "continue").status_code == 409  # nada que seguir todavía
    assert state(env, session_id)["waiting_for_conductor"] is False
    answer(env, token, "sadness")
    wait(env, 30)
    current = state(env, session_id)
    assert current["step_index"] == 0 and current["waiting_for_conductor"] is True
    # La persona sigue leyendo la emoción de la imagen mientras espera.
    assert view(env, token).json()["recognition"]["message"] == "Es tristeza"
    assert post(env, session_id, "continue").status_code == 200
    current = state(env, session_id)
    assert current["step_index"] == 1 and current["waiting_for_conductor"] is False
    assert post(env, session_id, "continue").status_code == 409


def test_esperar_tambien_tras_vencer_el_tiempo(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, _ = start(env, with_supports(env, [recognition(sad, exposure=5), recognition(sad)], pause="wait"))
    wait(env, 20)
    current = state(env, session_id)
    assert current["step_index"] == 0 and current["waiting_for_conductor"] is True
    assert post(env, session_id, "continue").status_code == 200
    assert state(env, session_id)["step_index"] == 1


def test_la_pantalla_recibe_solo_los_apoyos_de_presentacion(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, with_supports(env, [recognition(sad)], pictograms=True, read_aloud=True))
    assert view(env, token).json()["supports"] == {"pictograms": True, "large_controls": False, "read_aloud": True}
    assert state(env, session_id)["supports"]["read_aloud"] is True


def test_seguir_es_solo_de_quien_conduce(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = start(env, with_supports(env, [recognition(sad), recognition(sad)], pause="wait"))
    answer(env, token, "sadness")
    assert post(env, session_id, "continue", user=env.user_2).status_code in (403, 404)
    assert state(env, session_id)["step_index"] == 0


# --- Persistencia y migración ---------------------------------------------------------------


def test_ida_y_vuelta(factory):  # noqa: F811
    supports = ProtocolSupports(pictograms=True, read_aloud=True, no_time_limit=True, pause=PauseMode.WAIT)
    item = stored_protocol(supports=supports)
    PostgresProtocolRepository(factory).replace(item)
    found = PostgresProtocolRepository(factory).get("p1")
    assert found == item and found.supports == supports and found.accessible is True


def _run(engine, step: str) -> None:  # noqa: F811
    spec = importlib.util.spec_from_file_location("migration_20261106_38", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ("20261106_38", "20261106_37")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()


def test_migracion_el_modo_accesible_existente_queda_con_el_mismo_preajuste(engine, factory):  # noqa: F811
    PostgresProtocolRepository(factory).replace(stored_protocol(accessible=True))
    _run(engine, "downgrade")
    assert "support_pause" not in {column["name"] for column in inspect(engine).get_columns("protocols")}
    with engine.begin() as connection:
        assert connection.execute(text("SELECT accessible FROM protocols")).scalar_one()
    _run(engine, "upgrade")
    assert PostgresProtocolRepository(factory).get("p1").supports == ACCESSIBLE_PRESET
    test_ida_y_vuelta(factory)
