"""Persistencia del reconocimiento de emociones: pasos del protocolo, resultados
por paso y la migración 20261102_31 (SQLite en memoria, sin personas ni modelos)."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from emotv.domain.guided_session import RecognitionResult
from emotv.domain.protocol import ProtocolStep, StepKind
from emotv.infrastructure.persistence.in_memory_guided_repository import InMemoryGuidedSessionRepository
from emotv.infrastructure.persistence.models import ProtocolStepRecord, RecognitionResultRecord
from emotv.infrastructure.persistence.postgres_guided_repositories import PostgresGuidedSessionRepository
from emotv.infrastructure.persistence.postgres_practice_repositories import PostgresProtocolRepository
from emotv.shared.security.field_encryption import FieldCipher
from tests.integration.test_practice_persistence import T0, engine, factory, protocol  # noqa: F401
from tests.integration.test_privacy_accounts import KEY

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261102_31_recognition_steps.py"
RECOGNITION = ProtocolStep.recognition("s1", 12, 4, "happiness")


def result(**fields):
    base = dict(id="r1", session_id="ses1", step_index=3, stimulus_id="s1", target_expression="happiness",
                options=("sadness", "happiness", "fear", "anger"), outcome="answered", started_at=T0,
                ended_at=T0 + timedelta(seconds=4), chosen_expression="fear", seconds_to_answer=4.0,
                answered_by="conductor")
    return RecognitionResult(**{**base, **fields})


def with_recognition(factory):  # noqa: F811
    item = protocol(steps=(*protocol().steps, RECOGNITION))
    PostgresProtocolRepository(factory).replace(item)
    return item


def test_protocolo_con_reconocimiento_ida_y_vuelta(factory):  # noqa: F811
    item = with_recognition(factory)
    found = PostgresProtocolRepository(factory).get("p1")
    assert found == item and found.steps[3].kind is StepKind.RECOGNITION and found.steps[3].option_count == 4


@pytest.mark.parametrize("values", [
    {"kind": "recognition", "option_count": 3},                                   # sin respuesta correcta
    {"kind": "recognition", "target_expression": "happiness", "option_count": 5},
    {"kind": "recognition", "target_expression": "happiness", "option_count": 3, "hold_seconds": 2},
    {"kind": "recognition", "stimulus_id": None, "target_expression": "happiness", "option_count": 3},
    {"kind": "stimulus", "option_count": 3},
])
def test_la_base_rechaza_reconocimientos_incoherentes(factory, values):  # noqa: F811
    row = dict(id="x1", protocol_id="p1", position=9, stimulus_id="s1", exposure_seconds=10,
               capture_after_seconds=0, record_verbal_response=False, shown_before_analyzer=False)
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.add(ProtocolStepRecord(**{**row, **values}))


@pytest.fixture(params=["postgres", "memoria"])
def guided(request, factory):  # noqa: F811
    if request.param == "memoria":
        return InMemoryGuidedSessionRepository()
    return PostgresGuidedSessionRepository(factory, FieldCipher([KEY]))


def test_resultado_ida_y_vuelta_y_reemplazo(guided):
    timed_out = result(id="r2", step_index=4, outcome="timed_out", chosen_expression=None, seconds_to_answer=None,
                       answered_by=None)
    guided.save_recognition_result(timed_out)
    guided.save_recognition_result(result())
    assert guided.list_recognition_results("ses1") == (result(), timed_out)
    skipped = result(id="r9", outcome="skipped", chosen_expression=None, seconds_to_answer=None, answered_by=None)
    guided.save_recognition_result(skipped)
    found = guided.list_recognition_results("ses1")[0]
    assert replace(found, id=skipped.id) == skipped
    assert guided.list_recognition_results("otra") == ()


def test_la_base_exige_la_opcion_solo_si_se_respondio(factory):  # noqa: F811
    row = dict(id="x1", session_id="ses1", step_index=3, stimulus_id="s1", target_expression="happiness",
               options="happiness,sadness", outcome="timed_out", chosen_expression="sadness",
               seconds_to_answer=None, answered_by=None, started_at=T0, ended_at=T0)
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.add(RecognitionResultRecord(**row))


def test_borrar_la_sesion_borra_sus_resultados(factory):  # noqa: F811
    PostgresGuidedSessionRepository(factory, FieldCipher([KEY])).save_recognition_result(result())
    with factory.begin() as db:
        db.execute(text("DELETE FROM sessions WHERE id = 'ses1'"))
    with factory() as db:
        assert db.execute(text("SELECT COUNT(*) FROM recognition_results")).scalar() == 0


# --- Migración ----------------------------------------------------------------------------

def _migration():
    spec = importlib.util.spec_from_file_location("migration_20261102_31", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, step: str) -> None:  # noqa: F811
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), step)()


def test_migracion_sigue_al_segundo_factor():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261102_31", "20261102_30")


def test_migracion_downgrade_y_upgrade(engine, factory):  # noqa: F811
    with_recognition(factory)
    PostgresGuidedSessionRepository(factory, FieldCipher([KEY])).save_recognition_result(result())

    _run(engine, "downgrade")
    assert "recognition_results" not in inspect(engine).get_table_names()
    assert "option_count" not in {column["name"] for column in inspect(engine).get_columns("protocol_steps")}
    with engine.connect() as connection:
        kinds = connection.execute(text("SELECT kind FROM protocol_steps ORDER BY position")).scalars().all()
    # El reconocimiento se quita; los demás pasos quedan igual.
    assert kinds == ["stimulus", "practice", "practice"]

    _run(engine, "upgrade")
    assert "recognition_results" in inspect(engine).get_table_names()
    # La tabla recreada por esta migración recibe también la de los intentos (20261106_39).
    from tests.integration.test_step_attempts import bring_to_current
    bring_to_current(engine, "recognition_results")
    item = with_recognition(factory)
    assert PostgresProtocolRepository(factory).get("p1") == item
    guided = PostgresGuidedSessionRepository(factory, FieldCipher([KEY]))
    guided.save_recognition_result(result())
    assert guided.list_recognition_results("ses1") == (result(),)
