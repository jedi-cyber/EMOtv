"""Paso de práctica del protocolo y resultado de un ejercicio (sin personas ni modelos)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from emotv.domain.expression_info import EXPRESSION_KEYS
from emotv.domain.guided_session import PracticeOutcome, PracticeResult
from emotv.domain.protocol import MAX_HOLD_SECONDS, PRACTICE_TARGETS, Protocol, ProtocolStep, StepKind

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)


def practice(**fields):
    base = dict(stimulus_id=None, exposure_seconds=20, capture_after_seconds=0, kind="practice",
                target_expression="happiness", hold_seconds=2)
    return ProtocolStep(**{**base, **fields})


def result(**fields):
    base = dict(id="r1", session_id="s1", step_index=0, target_expression="happiness", outcome="achieved",
                peak_level=0.8, relative_to_calibration=True, feedback_visible=True, analyzed_frames=12,
                flagged_frames=1, emotion_model_id="hsemotion", emotion_model_version="1",
                started_at=T0, ended_at=T0 + timedelta(seconds=7), seconds_to_achieve=6.5)
    return PracticeResult(**{**base, **fields})


# --- Paso del protocolo ------------------------------------------------------------------

def test_un_paso_existente_es_de_estimulo_por_defecto():
    step = ProtocolStep("s1", 10, 5)
    assert step.kind is StepKind.STIMULUS and not step.is_practice
    assert step.target_expression is None and step.hold_seconds is None


def test_un_paso_de_estimulo_sigue_exigiendo_su_estimulo():
    for stimulus_id in (None, "", "  "):
        with pytest.raises(ValueError, match="indica un estímulo"):
            ProtocolStep(stimulus_id, 10, 5)


@pytest.mark.parametrize("fields", [{"target_expression": "happiness"}, {"hold_seconds": 2}])
def test_un_paso_de_estimulo_no_admite_campos_de_practica(fields):
    with pytest.raises(ValueError, match="no tiene expresión pedida"):
        ProtocolStep("s1", 10, 5, **fields)


def test_practica_valida_con_y_sin_ilustracion():
    plain = practice()
    assert plain.is_practice and plain.stimulus_id is None
    illustrated = ProtocolStep.practice("sadness", 3, 15, illustration_id=" s9 ")
    assert illustrated.kind is StepKind.PRACTICE and illustrated.stimulus_id == "s9"
    assert (illustrated.target_expression, illustrated.hold_seconds, illustrated.exposure_seconds) == ("sadness", 3, 15)
    assert practice(stimulus_id="").stimulus_id is None


def test_expresiones_que_se_pueden_pedir():
    # Todo el catálogo, incluido desprecio: quien arma el protocolo elige (§14.1).
    assert PRACTICE_TARGETS == EXPRESSION_KEYS and "contempt" in PRACTICE_TARGETS
    for target in PRACTICE_TARGETS:
        assert practice(target_expression=target).target_expression == target


@pytest.mark.parametrize("target", [None, "", "desprecio", "alegria", "HAPPINESS"])
def test_practica_exige_una_expresion_valida(target):
    with pytest.raises(ValueError, match="expresión que se pide"):
        practice(target_expression=target)


@pytest.mark.parametrize("hold, exposure", [(0, 20), (MAX_HOLD_SECONDS + 1, 30), (5, 5), (6, 5)])
def test_sosten_entre_uno_y_el_maximo_y_menor_que_el_tiempo(hold, exposure):
    with pytest.raises(ValueError):
        practice(hold_seconds=hold, exposure_seconds=exposure)


@pytest.mark.parametrize("hold", [None, 1.5, True, "2"])
def test_sosten_es_un_entero(hold):
    with pytest.raises(TypeError, match="hold_seconds"):
        practice(hold_seconds=hold)


def test_sosten_en_los_limites():
    assert practice(hold_seconds=1, exposure_seconds=2).hold_seconds == 1
    assert practice(hold_seconds=MAX_HOLD_SECONDS, exposure_seconds=MAX_HOLD_SECONDS + 1).hold_seconds == MAX_HOLD_SECONDS


@pytest.mark.parametrize("fields, message", [
    ({"capture_after_seconds": 3}, "captura automática"),
    ({"record_verbal_response": True}, "respuesta verbal"),
    ({"shown_before_analyzer": True}, "antes del analizador"),
    ({"exposure_seconds": 121}, "exposición dura"),
])
def test_practica_no_admite_campos_de_estimulo(fields, message):
    with pytest.raises(ValueError, match=message):
        practice(**fields)


def test_tipo_de_paso_desconocido():
    with pytest.raises(ValueError):
        ProtocolStep("s1", 10, 5, kind="video")


def test_un_protocolo_puede_tener_solo_practicas_o_combinarlas():
    base = dict(id="p1", family_id="f1", version=1, owner_user_id="u1", name="Práctica", description="",
                for_children=True, created_at=T0)
    only = Protocol(**base, steps=(practice(), practice(target_expression="surprise")))
    assert all(step.is_practice for step in only.steps)
    mixed = Protocol(**base, steps=(ProtocolStep("s1", 10, 5), practice()))
    assert [step.kind for step in mixed.steps] == [StepKind.STIMULUS, StepKind.PRACTICE]


def test_el_examen_sigue_sin_pasos():
    with pytest.raises(ValueError, match="no tiene estímulos"):
        Protocol(id="p1", family_id="f1", version=1, owner_user_id="u1", name="Examen", description="",
                 for_children=False, created_at=T0, kind="exam", steps=(practice(),))


# --- Resultado de un ejercicio ------------------------------------------------------------

def test_resultado_logrado():
    item = result()
    assert item.outcome is PracticeOutcome.ACHIEVED and item.achieved


@pytest.mark.parametrize("outcome", ["timed_out", "skipped", "stopped"])
def test_resultado_no_logrado_no_tiene_segundos(outcome):
    item = result(outcome=outcome, seconds_to_achieve=None)
    assert not item.achieved
    with pytest.raises(ValueError, match="Solo un ejercicio logrado"):
        result(outcome=outcome, seconds_to_achieve=3.0)


def test_logrado_exige_segundos_no_negativos():
    with pytest.raises(ValueError, match="Solo un ejercicio logrado"):
        result(seconds_to_achieve=None)
    with pytest.raises(ValueError, match="no son negativos"):
        result(seconds_to_achieve=-1.0)


@pytest.mark.parametrize("fields", [
    {"target_expression": "desprecio"},
    {"outcome": "failed"},
    {"peak_level": 1.2},
    {"peak_level": -0.1},
    {"step_index": -1},
    {"analyzed_frames": -1},
    {"flagged_frames": 1.0},
    {"id": ""},
    {"session_id": " "},
    {"ended_at": T0 - timedelta(seconds=1)},
])
def test_resultado_invalido(fields):
    with pytest.raises(ValueError):
        result(**fields)


@pytest.mark.parametrize("name", ["started_at", "ended_at"])
def test_resultado_exige_zona_horaria(name):
    with pytest.raises(ValueError, match="zona horaria"):
        result(**{name: datetime(2026, 10, 30, 9, 0, 10)})


def test_resultado_es_inmutable():
    with pytest.raises(AttributeError):
        result().peak_level = 0.1  # type: ignore[misc]


def test_cada_expresion_que_se_pide_tiene_su_instruccion():
    from emotv.domain.guided_session import PRACTICE_INSTRUCTIONS
    assert set(PRACTICE_INSTRUCTIONS) == set(PRACTICE_TARGETS)
    assert all(len(text.split()) <= 4 for text in PRACTICE_INSTRUCTIONS.values())
