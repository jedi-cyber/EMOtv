"""Bloque 2b, parte 2: repetir un reconocimiento o un ejercicio. Cada intento se
guarda; las métricas y las estadísticas cuentan solo el primero. Incluye la
migración 20261106_39 (SQLite en memoria, reloj falso; sin modelos ni personas)."""
from __future__ import annotations

from datetime import timedelta
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from emotv.domain.guided_session import MAX_STEP_ATTEMPTS, PracticeResult
from emotv.infrastructure.persistence.in_memory_guided_repository import InMemoryGuidedSessionRepository
from emotv.infrastructure.persistence.postgres_guided_repositories import PostgresGuidedSessionRepository
from emotv.shared.security.field_encryption import FieldCipher
from tests.integration.test_guided_sessions import post, state, view, wait
from tests.integration.test_practice_persistence import T0, engine, factory  # noqa: F401
from tests.integration.test_practice_persistence import result as practice_result
from tests.integration.test_privacy_accounts import KEY, env, headers  # noqa: F401
from tests.integration.test_protocol_supports import start, with_supports
from tests.integration.test_recognition_persistence import result as recognition_result
from tests.integration.test_recognition_sessions import answer, recognition, sad_stimulus

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261106_39_step_attempts.py"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_20261106_39", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bring_to_current(engine, table: str) -> None:  # noqa: F811
    """Para las pruebas de migraciones anteriores que recrean la tabla: le aplica esta."""
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            _migration().upgrade_table(table)


def _run(engine, step: str) -> None:  # noqa: F811
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), step)()


def repeat(env, session_id):  # noqa: F811
    return post(env, session_id, "repeat")


# --- Dominio y repositorio ----------------------------------------------------------------


def test_el_intento_va_de_1_al_maximo():
    assert recognition_result().attempt == 1
    assert recognition_result(attempt=MAX_STEP_ATTEMPTS).attempt == MAX_STEP_ATTEMPTS
    for wrong in (0, MAX_STEP_ATTEMPTS + 1, True):
        with pytest.raises(ValueError, match="intento"):
            recognition_result(attempt=wrong)
        with pytest.raises(ValueError, match="intento"):
            practice_result(attempt=wrong)


@pytest.fixture(params=["postgres", "memoria"])
def guided(request, factory):  # noqa: F811
    if request.param == "memoria":
        return InMemoryGuidedSessionRepository()
    return PostgresGuidedSessionRepository(factory, FieldCipher([KEY]))


def test_los_resultados_cuentan_el_primer_intento_y_los_intentos_guardan_todos(guided):
    first = recognition_result()
    second = recognition_result(id="r2", attempt=2, started_at=T0 + timedelta(seconds=9),
                                ended_at=T0 + timedelta(seconds=12), chosen_expression="happiness",
                                seconds_to_answer=3.0)
    guided.save_recognition_result(second)
    guided.save_recognition_result(first)
    assert guided.list_recognition_results("ses1") == (first,)
    assert guided.list_recognition_attempts("ses1") == (first, second)
    again = practice_result(id="q2", attempt=2)
    guided.save_practice_result(practice_result())
    guided.save_practice_result(again)
    assert guided.list_practice_results("ses1") == (practice_result(),)
    assert [item.attempt for item in guided.list_practice_attempts("ses1")] == [1, 2]


def test_la_base_no_admite_dos_veces_el_mismo_intento(factory):  # noqa: F811
    from emotv.infrastructure.persistence.models import RecognitionResultRecord
    row = dict(session_id="ses1", step_index=3, stimulus_id="s1", target_expression="happiness",
               options="happiness,sadness", outcome="timed_out", started_at=T0, ended_at=T0, attempt=2)
    with factory.begin() as db:
        db.add(RecognitionResultRecord(id="x1", **row))
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.add(RecognitionResultRecord(id="x2", **row))


# --- Motor y API --------------------------------------------------------------------------


def distractor(env, token):  # noqa: F811
    """Una opción mostrada que no es la emoción de la imagen (las distractoras son al azar)."""
    return next(item["key"] for item in view(env, token).json()["recognition"]["options"] if item["key"] != "sadness")


def _waiting_session(env):  # noqa: F811
    stimulus = sad_stimulus(env)
    item = with_supports(env, [recognition(stimulus, 10), recognition(stimulus, 10)], pause="wait")
    return start(env, item)


def test_repetir_un_reconocimiento_empieza_otra_vez_el_mismo_paso(env):  # noqa: F811
    session_id, token = _waiting_session(env)
    first = state(env, session_id)
    assert first["attempt"] == 1 and first["can_repeat"] is False and first["max_attempts"] == MAX_STEP_ATTEMPTS
    # Sin terminar el paso no se repite.
    assert repeat(env, session_id).status_code == 409
    options = view(env, token).json()["recognition"]["options"]
    exposure = view(env, token).json()["stimulus"]["exposure"]
    other = distractor(env, token)
    answer(env, token, other)
    assert state(env, session_id)["can_repeat"] is True

    assert repeat(env, session_id).status_code == 200
    again = state(env, session_id)
    assert again["step_index"] == 0 and again["attempt"] == 2 and again["can_repeat"] is False
    assert again["recognition"]["chosen_expression"] is None and again["waiting_for_conductor"] is False
    # La pantalla de la persona recibe otra exposición: vuelve a empezar el paso.
    assert view(env, token).json()["stimulus"]["exposure"] != exposure
    participant = view(env, token).json()["recognition"]
    # Las mismas opciones, sin la respuesta anterior.
    assert participant["options"] == options and participant["chosen"] is None and participant["message"] is None
    wait(env, 4)
    answer(env, token, "sadness")

    done = state(env, session_id)
    # Las métricas cuentan el primer intento; la repetición se describe aparte.
    assert [item["chosen_expression"] for item in done["recognition_results"]] == [other]
    repeated = done["repeated_attempts"]
    assert len(repeated) == 1 and repeated[0]["attempt"] == 2 and repeated[0]["step_kind"] == "recognition"
    assert repeated[0]["chosen_expression"] == "sadness" and repeated[0]["seconds_to_answer"] == pytest.approx(4.0)


def test_el_tercer_intento_es_el_ultimo(env):  # noqa: F811
    session_id, token = _waiting_session(env)
    for attempt in range(1, MAX_STEP_ATTEMPTS + 1):
        assert state(env, session_id)["attempt"] == attempt
        answer(env, token, "sadness")
        if attempt < MAX_STEP_ATTEMPTS:
            assert repeat(env, session_id).status_code == 200
    assert state(env, session_id)["can_repeat"] is False
    assert repeat(env, session_id).status_code == 409
    assert post(env, session_id, "continue").status_code == 200
    assert state(env, session_id)["step_index"] == 1 and state(env, session_id)["attempt"] == 1


def test_tambien_se_repite_un_paso_que_termino_sin_respuesta(env):  # noqa: F811
    stimulus = sad_stimulus(env)
    item = with_supports(env, [recognition(stimulus, 5)], pause="wait")
    session_id, token = start(env, item)
    wait(env, 6)
    assert state(env, session_id)["can_repeat"] is True
    assert repeat(env, session_id).status_code == 200
    answer(env, token, "sadness")
    done = state(env, session_id)
    assert done["recognition_results"][0]["outcome"] == "timed_out"
    assert done["repeated_attempts"][0]["outcome"] == "answered"


def test_la_linea_de_tiempo_empieza_en_el_primer_intento_y_lista_las_repeticiones(env):  # noqa: F811
    session_id, token = _waiting_session(env)
    wait(env, 2)
    other = distractor(env, token)
    answer(env, token, other)
    repeat(env, session_id)
    wait(env, 3)
    answer(env, token, "sadness")
    post(env, session_id, "continue")
    log = state(env, session_id)["steps_log"][0]
    assert log["step_index"] == 0
    timeline = env.client.get(f"/sessions/{session_id}/timeline", headers=headers(env, env.user_1))
    assert timeline.status_code == 200, timeline.text
    first = next(item for item in timeline.json()["lanes"]["stimuli"] if item["step_index"] == 0)
    assert first["start"] == pytest.approx(0, abs=0.01)
    assert first["chosen_expression"] == other
    assert first["repeats"] == [{"attempt": 2, "outcome": "answered", "chosen_expression": "sadness",
                                 "seconds_to_answer": pytest.approx(3.0)}]


def test_solo_quien_conduce_repite(env):  # noqa: F811
    session_id, token = _waiting_session(env)
    answer(env, token, "sadness")
    other = post(env, session_id, "repeat", user=env.user_2)
    assert other.status_code in (403, 404)
    assert state(env, session_id)["attempt"] == 1


# --- Migración ----------------------------------------------------------------------------


def test_migracion_sigue_a_los_apoyos():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261106_39", "20261106_38")


def test_migracion_downgrade_deja_el_primer_intento_y_upgrade_lo_marca_como_1(engine, factory):  # noqa: F811
    guided = PostgresGuidedSessionRepository(factory, FieldCipher([KEY]))
    guided.save_recognition_result(recognition_result())
    guided.save_recognition_result(recognition_result(id="r2", attempt=2))
    guided.save_practice_result(practice_result())
    _run(engine, "downgrade")
    for table in ("recognition_results", "practice_results"):
        assert "attempt" not in {column["name"] for column in inspect(engine).get_columns(table)}
    assert "step_attempt" not in {column["name"] for column in inspect(engine).get_columns("guided_runs")}
    _run(engine, "upgrade")
    assert guided.list_recognition_attempts("ses1") == (recognition_result(),)
    assert guided.list_practice_attempts("ses1") == (practice_result(),)
    assert isinstance(guided.list_practice_attempts("ses1")[0], PracticeResult)


def test_tambien_se_repite_un_ejercicio_de_practica(env):  # noqa: F811
    practice = {"kind": "practice", "target_expression": "happiness", "hold_seconds": 2, "exposure_seconds": 6}
    item = with_supports(env, [practice], pause="wait")
    session_id, _ = start(env, item)
    wait(env, 7)
    assert state(env, session_id)["can_repeat"] is True
    assert repeat(env, session_id).status_code == 200
    again = state(env, session_id)
    assert again["attempt"] == 2 and again["practice"]["achieved"] is False and again["remaining_seconds"] == 6
    wait(env, 7)
    done = state(env, session_id)
    assert [item["outcome"] for item in done["practice_results"]] == ["timed_out"]
    assert [(item["step_kind"], item["attempt"], item["outcome"]) for item in done["repeated_attempts"]] == [
        ("practice", 2, "timed_out")]
