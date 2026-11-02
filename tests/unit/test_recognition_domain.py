"""Reglas del paso de reconocimiento y de su resultado (sin base de datos)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from emotv.domain.guided_session import (
    RECOGNITION_ANSWERS,
    RECOGNITION_NAMES,
    RecognitionOutcome,
    RecognitionResult,
)
from emotv.domain.expression_info import EXPRESSION_KEYS
from emotv.domain.protocol import ProtocolStep, StepKind
from emotv.application.guided_session_service import GuidedSessionService

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)


def result(**fields):
    base = dict(id="r1", session_id="s1", step_index=0, stimulus_id="img", target_expression="sadness",
                options=("happiness", "sadness", "anger"), outcome="answered", started_at=NOW,
                ended_at=NOW + timedelta(seconds=3), chosen_expression="sadness", seconds_to_answer=3.0,
                answered_by="participant")
    return RecognitionResult(**{**base, **fields})


def test_un_reconocimiento_usa_una_imagen_y_entre_dos_y_cuatro_opciones():
    item = ProtocolStep.recognition("img", 10)
    assert item.kind is StepKind.RECOGNITION and item.is_recognition and not item.is_practice
    assert item.option_count == 3 and item.target_expression is None
    with pytest.raises(ValueError):
        ProtocolStep(None, 10, 0, kind="recognition", option_count=3)
    for count in (1, 5):
        with pytest.raises(ValueError, match="entre 2 y 4"):
            ProtocolStep.recognition("img", 10, count)
    with pytest.raises(ValueError):
        ProtocolStep("img", 10, 2, kind="recognition", option_count=3)        # sin captura automática
    with pytest.raises(ValueError):
        ProtocolStep("img", 10, 0, kind="recognition", option_count=3, hold_seconds=2)
    with pytest.raises(ValueError):
        ProtocolStep.recognition("img", 10, target_expression="pena")


def test_los_otros_pasos_no_tienen_opciones():
    with pytest.raises(ValueError):
        ProtocolStep("img", 10, 2, option_count=3)
    with pytest.raises(ValueError):
        ProtocolStep(None, 10, 0, kind="practice", target_expression="happiness", hold_seconds=2, option_count=3)


def test_el_resultado_respondido_registra_la_opcion_y_si_coincidio():
    assert result().matched is True
    assert result(chosen_expression="anger").matched is False
    unanswered = result(outcome="timed_out", chosen_expression=None, seconds_to_answer=None, answered_by=None)
    assert unanswered.outcome is RecognitionOutcome.TIMED_OUT and unanswered.matched is None
    with pytest.raises(ValueError):
        result(chosen_expression="fear")                                      # no se mostró
    with pytest.raises(ValueError):
        result(options=("happiness", "anger"))                                # falta la de la imagen
    with pytest.raises(ValueError):
        result(outcome="skipped")                                             # sin respuesta no hay opción
    with pytest.raises(ValueError):
        result(options=("sadness", "sadness"))


def test_las_opciones_son_estables_e_incluyen_la_de_la_imagen():
    for target in EXPRESSION_KEYS:
        step = ProtocolStep.recognition("img", 10, 4, target)
        options = GuidedSessionService._recognition_options("sesion", 0, step)
        assert options == GuidedSessionService._recognition_options("sesion", 0, step)
        assert len(set(options)) == 4 and target in options
        assert target == "contempt" or "contempt" not in options


def test_cada_expresion_tiene_nombre_y_mensaje():
    assert set(RECOGNITION_NAMES) == set(EXPRESSION_KEYS) == set(RECOGNITION_ANSWERS)
