"""Persistencia de exámenes simulados y del tipo de protocolo (SQLite en memoria)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.domain import Role, User
from emotv.domain.exam import Exam, ExamState
from emotv.domain.protocol import Protocol, ProtocolKind, ProtocolStep
from emotv.domain.session import EmotionalSession
from emotv.domain.stimulus import Stimulus
from emotv.infrastructure.persistence.models import Base
from emotv.infrastructure.persistence.postgres_exam_repository import PostgresExamRepository
from emotv.infrastructure.persistence.postgres_practice_repositories import (
    PostgresProtocolRepository,
    PostgresStimulusRepository,
)
from emotv.infrastructure.persistence.postgres_session_repository import PostgresSessionRepository
from emotv.infrastructure.persistence.postgres_user_repository import PostgresUserRepository

T0 = datetime(2026, 10, 29, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    PostgresUserRepository(factory).save(User("d1", "docente@example.com", "hash", Role.PSYCHOLOGIST, T0))
    PostgresProtocolRepository(factory).add(Protocol(
        id="p1", family_id="f1", version=1, owner_user_id="d1", name="Examen simulado", description="",
        for_children=False, created_at=T0, kind=ProtocolKind.EXAM))
    return factory


def test_protocolo_de_examen_se_guarda_con_su_tipo(factory):
    found = PostgresProtocolRepository(factory).get("p1")
    assert found.kind is ProtocolKind.EXAM
    assert found.steps == ()


def test_protocolo_de_practica_conserva_su_tipo(factory):
    PostgresStimulusRepository(factory).add(Stimulus(
        id="s1", title="Paisaje", kind="emotional", category="c", intensity="mild", min_age=5, origin="Propio",
        license="Uso docente", scope="group", owner_user_id="d1", content_type="image/png", created_at=T0,
        expected_expression="happiness"), b"png")
    repository = PostgresProtocolRepository(factory)
    repository.add(Protocol(id="p2", family_id="f2", version=1, owner_user_id="d1", name="Práctica",
                            description="", for_children=False, created_at=T0, steps=(ProtocolStep("s1", 10, 5),)))
    assert repository.get("p2").kind is ProtocolKind.PRACTICE


def test_examen_ida_y_vuelta(factory):
    exams = PostgresExamRepository(factory)
    exam = exams.save(Exam(id="e1", owner_user_id="d1", protocol_id="p1", join_code="ABC234", created_at=T0))
    assert exams.get("e1") == exam
    assert exams.get_by_join_code("abc234") == exam
    assert exams.join_code_exists("ABC234")
    assert not exams.join_code_exists("XYZ789")

    started = replace(exam, state=ExamState.IN_PROGRESS, consent_confirmed_at=T0 + timedelta(minutes=2),
                      started_at=T0 + timedelta(minutes=3))
    exams.save(started)
    closed = replace(started, state=ExamState.CLOSED, closed_at=T0 + timedelta(minutes=50))
    exams.save(closed)
    assert exams.get("e1") == closed
    assert exams.list_by_owner("d1") == (closed,)
    assert exams.list_by_owner("otro") == ()


def test_codigo_de_union_unico(factory):
    exams = PostgresExamRepository(factory)
    exams.save(Exam(id="e1", owner_user_id="d1", protocol_id="p1", join_code="ABC234", created_at=T0))
    with pytest.raises(IntegrityError):
        exams.save(Exam(id="e2", owner_user_id="d1", protocol_id="p1", join_code="ABC234", created_at=T0))


def test_sesiones_de_las_estaciones(factory):
    exams, sessions = PostgresExamRepository(factory), PostgresSessionRepository(factory)
    exams.save(Exam(id="e1", owner_user_id="d1", protocol_id="p1", join_code="ABC234", created_at=T0))
    first = sessions.save(EmotionalSession(id="s1", started_at=T0 + timedelta(seconds=1), owner_user_id="d1",
                                           session_type="adulto", protocol_id="p1", code="S-AAAAAA", exam_id="e1"))
    second = sessions.save(EmotionalSession(id="s2", started_at=T0 + timedelta(seconds=2), owner_user_id="d1",
                                            session_type="adulto", protocol_id="p1", code="S-BBBBBB", exam_id="e1"))
    sessions.save(EmotionalSession(id="s3", started_at=T0, owner_user_id="d1", code="S-CCCCCC"))
    assert exams.list_sessions("e1") == (first, second)
    assert sessions.get_by_id("s1").exam_id == "e1"
    assert sessions.get_by_id("s3").exam_id is None


def test_un_examen_con_sesiones_no_se_borra(factory):
    from emotv.infrastructure.persistence.models import ExamRecord

    PostgresExamRepository(factory).save(Exam(id="e1", owner_user_id="d1", protocol_id="p1", join_code="ABC234",
                                              created_at=T0))
    PostgresSessionRepository(factory).save(EmotionalSession(id="s1", started_at=T0, owner_user_id="d1",
                                                             code="S-AAAAAA", exam_id="e1"))
    with pytest.raises(IntegrityError):
        with factory.begin() as db:
            db.delete(db.get(ExamRecord, "e1"))
