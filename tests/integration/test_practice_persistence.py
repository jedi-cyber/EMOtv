"""Persistencia de la práctica de expresiones: pasos del protocolo, resultados por
ejercicio y la migración 20261030_28 (SQLite en memoria, sin personas ni modelos)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.domain import Role, User
from emotv.domain.guided_session import PracticeResult
from emotv.domain.protocol import Protocol, ProtocolKind, ProtocolStep, StepKind
from emotv.domain.session import EmotionalSession
from emotv.domain.stimulus import Stimulus
from emotv.infrastructure.persistence.in_memory_guided_repository import InMemoryGuidedSessionRepository
from emotv.infrastructure.persistence.models import Base, ProtocolStepRecord
from emotv.infrastructure.persistence.postgres_guided_repositories import PostgresGuidedSessionRepository
from emotv.infrastructure.persistence.postgres_practice_repositories import (
    PostgresProtocolRepository,
    PostgresStimulusRepository,
)
from emotv.infrastructure.persistence.postgres_session_repository import PostgresSessionRepository
from emotv.infrastructure.persistence.postgres_user_repository import PostgresUserRepository
from emotv.shared.security.field_encryption import FieldCipher
from tests.integration.test_privacy_accounts import KEY

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261030_28_practice_steps.py"


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def factory(engine):
    factory = sessionmaker(engine, expire_on_commit=False)
    PostgresUserRepository(factory).save(User("u1", "usuario@example.com", "hash", Role.STUDENT, T0))
    PostgresStimulusRepository(factory).add(Stimulus(
        id="s1", title="Paisaje", kind="emotional", category="c", intensity="mild", min_age=5, origin="Propio",
        license="Uso docente", scope="group", owner_user_id="u1", content_type="image/png", created_at=T0,
        expected_expression="happiness"), b"png")
    PostgresProtocolRepository(factory).add(protocol())
    PostgresSessionRepository(factory).save(EmotionalSession(
        id="ses1", started_at=T0, owner_user_id="u1", session_type="infantil", protocol_id="p1", code="S-AAAAAA"))
    return factory


def protocol(**fields):
    base = dict(id="p1", family_id="f1", version=1, owner_user_id="u1", name="Práctica", description="",
                for_children=True, created_at=T0,
                steps=(ProtocolStep("s1", 10, 5),
                       ProtocolStep.practice("happiness", 2, 20),
                       ProtocolStep.practice("surprise", 3, 15, illustration_id="s1")))
    return Protocol(**{**base, **fields})


def result(**fields):
    base = dict(id="r1", session_id="ses1", step_index=1, target_expression="happiness", outcome="achieved",
                peak_level=0.82, relative_to_calibration=True, feedback_visible=True, analyzed_frames=14,
                flagged_frames=2, emotion_model_id="hsemotion", emotion_model_version="1",
                started_at=T0, ended_at=T0 + timedelta(seconds=8), seconds_to_achieve=7.5)
    return PracticeResult(**{**base, **fields})


# --- Pasos del protocolo ---------------------------------------------------------------

def test_protocolo_con_practicas_ida_y_vuelta(factory):
    found = PostgresProtocolRepository(factory).get("p1")
    assert found == protocol()
    assert [step.kind for step in found.steps] == [StepKind.STIMULUS, StepKind.PRACTICE, StepKind.PRACTICE]
    assert found.steps[1].stimulus_id is None and found.steps[2].stimulus_id == "s1"


def test_protocolo_de_examen_no_cambia(factory):
    repository = PostgresProtocolRepository(factory)
    repository.add(Protocol(id="p2", family_id="f2", version=1, owner_user_id="u1", name="Examen",
                            description="", for_children=False, created_at=T0, kind=ProtocolKind.EXAM))
    found = repository.get("p2")
    assert found.kind is ProtocolKind.EXAM and found.steps == ()


@pytest.mark.parametrize("values", [
    {"stimulus_id": None, "kind": "stimulus"},
    {"kind": "practice"},
    {"kind": "stimulus", "target_expression": "happiness", "hold_seconds": 2},
    {"stimulus_id": None, "kind": "practice", "target_expression": "happiness", "hold_seconds": 10},
    {"stimulus_id": None, "kind": "practice", "target_expression": "happiness", "hold_seconds": 2,
     "capture_after_seconds": 3},
    {"kind": "video"},
])
def test_la_base_rechaza_pasos_incoherentes(factory, values):
    row = dict(id="x1", protocol_id="p1", position=9, stimulus_id="s1", exposure_seconds=10,
               capture_after_seconds=0, record_verbal_response=False, shown_before_analyzer=False)
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.add(ProtocolStepRecord(**{**row, **values}))


# --- Resultados por ejercicio -------------------------------------------------------------

@pytest.fixture(params=["postgres", "memoria"])
def guided(request, factory):
    if request.param == "memoria":
        return InMemoryGuidedSessionRepository()
    return PostgresGuidedSessionRepository(factory, FieldCipher([KEY]))


def test_resultado_ida_y_vuelta(guided):
    timed_out = result(id="r2", step_index=2, target_expression="surprise", outcome="timed_out",
                       seconds_to_achieve=None, peak_level=0.31, relative_to_calibration=False,
                       feedback_visible=False)
    guided.save_practice_result(timed_out)
    guided.save_practice_result(result())
    assert guided.list_practice_results("ses1") == (result(), timed_out)
    assert guided.list_practice_results("otra") == ()


def test_guardar_el_mismo_paso_reemplaza(guided):
    guided.save_practice_result(result())
    skipped = result(id="r9", outcome="skipped", seconds_to_achieve=None, peak_level=0.2)
    guided.save_practice_result(skipped)
    [found] = guided.list_practice_results("ses1")
    assert replace(found, id=skipped.id) == skipped


def test_la_base_exige_segundos_solo_si_se_logro(factory):
    from emotv.infrastructure.persistence.models import PracticeResultRecord
    row = dict(id="x1", session_id="ses1", step_index=1, target_expression="happiness", outcome="timed_out",
               seconds_to_achieve=3.0, peak_level=0.5, relative_to_calibration=True, feedback_visible=True,
               analyzed_frames=1, flagged_frames=0, emotion_model_id="m", emotion_model_version="1",
               started_at=T0, ended_at=T0)
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.add(PracticeResultRecord(**row))


def test_borrar_la_sesion_borra_sus_resultados(factory):
    PostgresGuidedSessionRepository(factory, FieldCipher([KEY])).save_practice_result(result())
    with factory.begin() as db:
        db.execute(text("DELETE FROM sessions WHERE id = 'ses1'"))
    with factory() as db:
        assert db.execute(text("SELECT COUNT(*) FROM practice_results")).scalar() == 0


# --- Migración ----------------------------------------------------------------------------

def _migration():
    spec = importlib.util.spec_from_file_location("migration_20261030_28", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, step: str) -> None:
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(_migration(), step)()


def _step_columns(engine) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns("protocol_steps")}


def test_migracion_sigue_a_la_de_estaciones():
    module = _migration()
    assert (module.revision, module.down_revision) == ("20261030_28", "20261030_27")


def test_migracion_downgrade_y_upgrade(engine, factory):
    PostgresGuidedSessionRepository(factory, FieldCipher([KEY])).save_practice_result(result())

    _run(engine, "downgrade")
    assert "practice_results" not in inspect(engine).get_table_names()
    assert not _step_columns(engine) & {"kind", "target_expression", "hold_seconds"}
    with engine.connect() as connection:
        # Solo quedan los pasos de estímulo, sin cambios.
        rows = connection.execute(text("SELECT position, stimulus_id, exposure_seconds, capture_after_seconds "
                                       "FROM protocol_steps")).all()
    assert [tuple(row) for row in rows] == [(0, "s1", 10, 5)]
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO protocol_steps (id, protocol_id, position, stimulus_id, exposure_seconds, "
                "capture_after_seconds, record_verbal_response, shown_before_analyzer) "
                "VALUES ('x0', 'p1', 5, NULL, 10, 0, 0, 0)"))

    _run(engine, "upgrade")
    assert "practice_results" in inspect(engine).get_table_names()
    assert {"kind", "target_expression", "hold_seconds"} <= _step_columns(engine)
    found = PostgresProtocolRepository(factory).get("p1")
    # Los pasos existentes quedan como estímulos, igual que antes.
    assert found.steps == (ProtocolStep("s1", 10, 5),)
    PostgresProtocolRepository(factory).replace(protocol())
    assert PostgresProtocolRepository(factory).get("p1") == protocol()
    guided = PostgresGuidedSessionRepository(factory, FieldCipher([KEY]))
    guided.save_practice_result(result())
    assert guided.list_practice_results("ses1") == (result(),)
    for values in ({"stimulus_id": None, "kind": "stimulus"},
                   # Las restricciones anteriores siguen vigentes.
                   {"stimulus_id": "s1", "kind": "stimulus", "exposure_seconds": 200}):
        with pytest.raises(IntegrityError):
            with factory.begin() as db:
                db.add(ProtocolStepRecord(**{"id": "x2", "protocol_id": "p1", "position": 9, "exposure_seconds": 10,
                                             "capture_after_seconds": 0, "record_verbal_response": False,
                                             "shown_before_analyzer": False, **values}))


# --- Señal de la práctica (20261030_29) -------------------------------------------------

def _run_29(engine, step: str) -> None:
    path = MIGRATION.with_name("20261030_29_practice_feedback.py")
    spec = importlib.util.spec_from_file_location("migration_20261030_29", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ("20261030_29", "20261030_28")
    with engine.connect() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()
        connection.commit()


def test_la_senal_de_la_practica_ida_y_vuelta_y_su_migracion(engine, factory):
    from emotv.domain.guided_session import GuidedRun
    guided = PostgresGuidedSessionRepository(factory, FieldCipher([KEY]))
    run = guided.save_run(GuidedRun(session_id="ses1", owner_user_id="u1", created_at=T0))
    assert guided.get_run("ses1").practice_feedback is True
    guided.save_run(replace(run, practice_feedback=False))
    assert guided.get_run("ses1").practice_feedback is False

    _run_29(engine, "downgrade")
    assert "practice_feedback" not in {column["name"] for column in inspect(engine).get_columns("guided_runs")}
    _run_29(engine, "upgrade")
    # Las sesiones que ya existían quedan con la señal encendida.
    assert guided.get_run("ses1").practice_feedback is True
