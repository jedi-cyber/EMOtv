"""Frases y totales de los ejercicios de práctica (sin personas, modelos ni base de datos)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from emotv.application.session_metrics import (
    practice_by_target,
    practice_metrics,
    practice_sentence,
    practice_totals,
    stimulus_metrics,
)
from emotv.domain.guided_session import PRACTICE_NOTICE, PracticeResult
from emotv.domain.protocol import ProtocolStep

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)
FORBIDDEN = ("bien", "mal ", "fracas", "falló", "excelente", "diagn", "trist", "sinti")


def result(step_index, outcome="achieved", target="happiness", seconds=None, visible=True):
    if outcome == "achieved" and seconds is None:
        seconds = 3.0
    return PracticeResult(
        id=f"r{step_index}", session_id="s1", step_index=step_index, target_expression=target, outcome=outcome,
        peak_level=0.8 if outcome == "achieved" else 0.3, relative_to_calibration=True, feedback_visible=visible,
        analyzed_frames=10, flagged_frames=0, emotion_model_id="m", emotion_model_version="1",
        started_at=T0, ended_at=T0 + timedelta(seconds=10), seconds_to_achieve=seconds if outcome == "achieved" else None)


STEPS = (ProtocolStep.practice("happiness", 2, 20), ProtocolStep.practice("surprise", 2, 20),
         ProtocolStep("img", 8, 4), ProtocolStep.practice("happiness", 3, 20), ProtocolStep.practice("sadness", 2, 20))


def test_frase_y_promedio_solo_con_los_logrados():
    metrics = practice_metrics(STEPS, [result(0, seconds=2.0), result(1, "timed_out", "surprise"),
                                       result(3, seconds=5.0), result(4, "timed_out", "sadness")])
    totals = metrics["totals"]
    assert totals["sentence"] == "Logró la expresión pedida en 2 de 4 ejercicios."
    assert totals["average_seconds_to_achieve"] == 3.5
    assert totals["average_sentence"] == "Tiempo promedio hasta lograrla: 3,5 s (solo los ejercicios logrados)."
    assert (totals["exercises"], totals["applied"], totals["achieved"], totals["not_reached"]) == (4, 4, 2, 0)
    assert metrics["notice"] == PRACTICE_NOTICE
    # La imagen no es un ejercicio.
    assert [item["step_index"] for item in metrics["exercises"]] == [0, 1, 3, 4]


def test_desglose_por_expresion_pedida_en_el_orden_del_catalogo():
    rows = practice_by_target([result(4, "timed_out", "sadness"), result(0, seconds=2.0), result(3, seconds=4.0),
                               result(1, "skipped", "surprise")])
    assert [row["target_expression"] for row in rows] == ["happiness", "surprise", "sadness"]
    happiness, surprise, sadness = rows
    assert (happiness["achieved"], happiness["applied"], happiness["average_seconds_to_achieve"]) == (2, 2, 3.0)
    assert (surprise["applied"], surprise["skipped"], surprise["average_seconds_to_achieve"]) == (0, 1, None)
    assert (sadness["achieved"], sadness["applied"]) == (0, 1)


def test_ningun_logro():
    totals = practice_totals([result(0, "timed_out"), result(1, "timed_out", "surprise")])
    assert totals["sentence"] == "Logró la expresión pedida en 0 de 2 ejercicios."
    assert totals["average_seconds_to_achieve"] is None and totals["average_sentence"] is None


def test_un_solo_ejercicio_en_singular():
    assert practice_sentence(1, 1) == "Logró la expresión pedida en 1 de 1 ejercicio."


def test_los_saltados_no_cuentan_y_se_informan_aparte():
    totals = practice_totals([result(0), result(1, "skipped", "surprise")])
    assert totals["sentence"] == "Logró la expresión pedida en 1 de 1 ejercicio."
    assert (totals["applied"], totals["skipped"]) == (1, 1)


def test_todos_saltados():
    totals = practice_totals([result(0, "skipped"), result(1, "skipped", "surprise")])
    assert totals["sentence"] == "Ningún ejercicio de práctica llegó a terminar."
    assert totals["feedback_sentence"] is None and totals["average_sentence"] is None


def test_sesion_detenida_deja_uno_a_medias_y_los_demas_sin_aplicar():
    metrics = practice_metrics(STEPS, [result(0, seconds=2.0), result(1, "stopped", "surprise")])
    totals = metrics["totals"]
    assert totals["sentence"] == "Logró la expresión pedida en 1 de 1 ejercicio."
    assert (totals["stopped"], totals["not_reached"], totals["exercises"]) == (1, 2, 4)
    assert [item["outcome"] for item in metrics["exercises"]] == ["achieved", "stopped", None, None]
    assert metrics["exercises"][2]["feedback_visible"] is None


def test_sesion_detenida_antes_de_empezar():
    metrics = practice_metrics(STEPS, [])
    assert metrics["totals"]["sentence"] == "Ningún ejercicio de práctica llegó a terminar."
    assert metrics["totals"]["not_reached"] == 4 and metrics["by_target"] == []


def test_indica_si_la_senal_visual_estuvo_activa():
    assert practice_totals([result(0), result(1, visible=True)])["feedback_sentence"] == \
        "La señal visual estuvo activa en todos los ejercicios."
    assert practice_totals([result(0, visible=False)])["feedback_sentence"] == \
        "La señal visual estuvo apagada en todos los ejercicios."
    assert practice_totals([result(0, visible=False), result(1), result(2, "timed_out")])["feedback_sentence"] == \
        "La señal visual estuvo activa en 2 de 3 ejercicios."
    # Un saltado no cuenta en la señal.
    assert practice_totals([result(0), result(1, "skipped", visible=False)])["feedback_visible"] == 1


def test_sin_ejercicios_no_hay_seccion_de_practica():
    assert practice_metrics((ProtocolStep("img", 8, 4),), []) is None


def test_no_se_mezcla_con_la_coincidencia_de_estimulos():
    metrics = stimulus_metrics(STEPS, {"img": None}, ())
    assert metrics["totals"]["emotional_stimuli"] == 0 and "practice" not in metrics["totals"]


def test_las_frases_describen_y_no_valoran():
    texts = [practice_sentence(0, 3), practice_sentence(3, 3), practice_sentence(0, 0), PRACTICE_NOTICE,
             *(value for value in practice_totals([result(0), result(1, "timed_out", visible=False)]).values()
               if isinstance(value, str))]
    for text in texts:
        assert not any(word in text.lower() for word in FORBIDDEN), text
    assert "rostros de adultos" in PRACTICE_NOTICE and "con niños no está validada" in PRACTICE_NOTICE
    assert "no el estado emocional" in PRACTICE_NOTICE
