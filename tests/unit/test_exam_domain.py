"""Examen simulado: protocolo de tipo examen y entidad examen (sin personas ni modelos)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from emotv.domain.exam import Exam, ExamState
from emotv.domain.protocol import Protocol, ProtocolKind, ProtocolStep
from emotv.domain.session import EmotionalSession

T0 = datetime(2026, 10, 29, 9, 0, tzinfo=timezone.utc)


def protocol(**fields):
    base = dict(id="p1", family_id="f1", version=1, owner_user_id="d1", name="Examen simulado", description="",
                for_children=False, created_at=T0, kind="exam")
    return Protocol(**{**base, **fields})


def exam(**fields):
    base = dict(id="e1", owner_user_id="d1", protocol_id="p1", join_code="ABC234", created_at=T0)
    return Exam(**{**base, **fields})


def test_protocolo_de_examen_sin_pasos_ni_cuestionarios():
    item = protocol()
    assert item.kind is ProtocolKind.EXAM
    assert item.steps == ()


@pytest.mark.parametrize("fields", [
    {"steps": (ProtocolStep("s1", 10, 5),)},
    {"pre_questionnaire_id": "q1"},
    {"post_questionnaire_id": "q2"},
])
def test_protocolo_de_examen_no_configura_pasos_ni_cuestionarios(fields):
    with pytest.raises(ValueError, match="no tiene estímulos ni cuestionarios"):
        protocol(**fields)


def test_protocolo_de_examen_es_solo_para_adultos():
    with pytest.raises(ValueError, match="solo para personas adultas"):
        protocol(for_children=True)


def test_protocolo_de_practica_sigue_igual():
    assert protocol(kind="practice", steps=(ProtocolStep("s1", 10, 5),)).kind is ProtocolKind.PRACTICE
    # Sin indicar el tipo, un protocolo es de práctica y sigue exigiendo estímulos.
    with pytest.raises(ValueError, match="entre 1 y"):
        Protocol(id="p", family_id="f", version=1, owner_user_id="d", name="Práctica", description="",
                 for_children=False, created_at=T0)


def test_examen_abierto_normaliza_el_codigo():
    item = exam(join_code=" abc234 ")
    assert item.join_code == "ABC234"
    assert item.state is ExamState.OPEN
    assert item.accepts_stations


@pytest.mark.parametrize("code", ["ABC23", "ABC2345", "ABC10O", "AB-234", ""])
def test_codigo_de_union_invalido(code):
    with pytest.raises(ValueError, match="código del examen"):
        exam(join_code=code)


def test_estados_del_examen_exigen_sus_horas():
    started = exam(state="in_progress", started_at=T0 + timedelta(minutes=5))
    closed = exam(state="closed", started_at=started.started_at, closed_at=T0 + timedelta(minutes=50))
    assert started.accepts_stations
    assert not closed.accepts_stations
    with pytest.raises(ValueError, match="en curso"):
        exam(state="in_progress")
    with pytest.raises(ValueError, match="sin iniciar"):
        exam(started_at=T0)
    with pytest.raises(ValueError, match="terminado"):
        exam(state="closed")
    with pytest.raises(ValueError, match="terminado"):
        exam(closed_at=T0)
    with pytest.raises(ValueError, match="antes de empezar"):
        exam(state="closed", started_at=T0 + timedelta(minutes=5), closed_at=T0 + timedelta(minutes=1))


def test_examen_terminado_sin_iniciar():
    assert exam(state="closed", closed_at=T0 + timedelta(minutes=1)).state is ExamState.CLOSED


def test_horas_con_zona_horaria():
    with pytest.raises(ValueError, match="zona horaria"):
        exam(created_at=datetime(2026, 10, 29, 9, 0))


def test_sesion_de_una_estacion_guarda_su_examen():
    session = EmotionalSession(id="s1", started_at=T0, exam_id=" e1 ")
    assert session.exam_id == "e1"
    assert EmotionalSession(id="s2", started_at=T0).exam_id is None
