"""Métricas descriptivas por estímulo de una sesión.

El sistema describe; no interpreta. Los textos dicen lo que ocurrió ("en 3 de 5
estímulos la expresión estimada coincidió con la esperada") y nunca valoran a la
persona. Los ejercicios de práctica se resumen aparte ("logró la expresión
pedida en 2 de 3 ejercicios") y nunca se mezclan con la coincidencia de estímulos.
Los reconocimientos también van aparte ("eligió la emoción de la imagen en 3 de 4
ejercicios"). Las capturas de mala calidad se muestran, pero no cuentan en los
totales. Las imágenes abstractas no tienen métricas de coincidencia.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from emotv.domain.guided_session import (
    ABSTRACT_NOTICE,
    PRACTICE_NOTICE,
    CaptureQuality,
    ExpressionCapture,
    RECOGNITION_NOTICE,
    PracticeOutcome,
    PracticeResult,
    RecognitionOutcome,
    RecognitionResult,
    VerbalResponse,
)
from emotv.domain.expression_info import EXPRESSION_KEYS
from emotv.domain.protocol import PRACTICE_TARGETS, ProtocolStep
from emotv.domain.stimulus import Stimulus, StimulusKind


def _capture(item: ExpressionCapture, expected: str | None) -> dict[str, Any]:
    data = {
        "id": item.id,
        "captured_at": item.captured_at.isoformat(),
        "emotion": item.emotion,
        "probability": item.confidence,
        "seconds_since_stimulus": item.seconds_since_stimulus,
        "quality": item.quality.value,
        "quality_issues": [issue.value for issue in item.quality_issues],
        # Una captura marcada se muestra, pero no cuenta en los totales.
        "counted": item.quality is CaptureQuality.GOOD and item.emotion is not None,
    }
    if expected is not None:
        data["matches_expected"] = item.emotion == expected if item.emotion is not None else None
    return data


def coincidence_sentence(matched: int, counted: int) -> str:
    if counted == 0:
        return "Ningún estímulo emocional tuvo una captura de buena calidad para comparar."
    noun = "estímulo" if counted == 1 else "estímulos"
    return f"En {matched} de {counted} {noun} la expresión estimada coincidió con la esperada."


def stimulus_metrics(
    steps: Sequence[ProtocolStep],
    stimuli: dict[str, Stimulus | None],
    captures: Iterable[ExpressionCapture],
    verbal: Iterable[VerbalResponse] = (),
    skipped: Iterable[int] = (),
) -> dict[str, Any]:
    """Métricas de una sesión: por estímulo emocional, la primera captura de
    buena calidad decide si coincidió; los estímulos sin ella no cuentan."""
    by_step: dict[int, list[ExpressionCapture]] = {}
    for item in captures:
        by_step.setdefault(item.step_index, []).append(item)
    said = {item.step_index: item.text for item in verbal}
    skipped = set(skipped)
    emotional, abstract = [], []
    for index, step in enumerate(steps):
        if step.is_practice or step.is_recognition:
            continue  # ilustración o pregunta: no cuenta en las coincidencias de expresión
        stimulus = stimuli.get(step.stimulus_id)
        if stimulus is None:
            continue
        items = sorted(by_step.get(index, []), key=lambda item: item.captured_at)
        base = {"step_index": index, "stimulus_id": stimulus.id, "title": stimulus.title,
                "category": stimulus.category, "skipped": index in skipped}
        if stimulus.kind is StimulusKind.ABSTRACT:
            # Solo lo capturado y lo que dijo ver: sin coincidencias.
            abstract.append({**base, "captures": [_capture(item, None) for item in items],
                             "said": said.get(index), "shown_before_analyzer": step.shown_before_analyzer})
            continue
        expected = stimulus.expected_expression
        rows = [_capture(item, expected) for item in items]
        counted = next((row for row in rows if row["counted"]), None)
        emotional.append({**base, "expected_expression": expected, "captures": rows,
                          "counted": counted is not None,
                          "matches_expected": counted["matches_expected"] if counted else None,
                          "excluded_captures": sum(1 for row in rows if not row["counted"])})
    counted = [item for item in emotional if item["counted"]]
    matched = sum(1 for item in counted if item["matches_expected"])
    return {
        "emotional": emotional,
        "abstract": abstract,
        "totals": {
            "emotional_stimuli": len(emotional),
            "counted": len(counted),
            "matched": matched,
            "excluded_captures": sum(item["excluded_captures"] for item in emotional),
            "sentence": coincidence_sentence(matched, len(counted)),
        },
        "abstract_notice": ABSTRACT_NOTICE if abstract else None,
    }


# --- Ejercicios de práctica ----------------------------------------------------------------
# Van aparte de la coincidencia de estímulos: aquí «coincidir con la pedida» es lo
# que se busca. Un ejercicio cuenta cuando llegó a su final (logrado o con el tiempo
# vencido); los saltados y los que quedaron a medias al detener la sesión se
# informan aparte y no cuentan.

APPLIED = (PracticeOutcome.ACHIEVED, PracticeOutcome.TIMED_OUT)


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _seconds_text(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def practice_sentence(achieved: int, applied: int) -> str:
    if applied == 0:
        return "Ningún ejercicio de práctica llegó a terminar."
    noun = "ejercicio" if applied == 1 else "ejercicios"
    return f"Logró la expresión pedida en {achieved} de {applied} {noun}."


def average_sentence(average: float | None) -> str | None:
    if average is None:
        return None
    return f"Tiempo promedio hasta lograrla: {_seconds_text(average)} s (solo los ejercicios logrados)."


def feedback_sentence(visible: int, applied: int) -> str | None:
    if applied == 0:
        return None
    if visible == applied:
        return "La señal visual estuvo activa en todos los ejercicios."
    if visible == 0:
        return "La señal visual estuvo apagada en todos los ejercicios."
    return f"La señal visual estuvo activa en {visible} de {applied} ejercicios."


def practice_totals(results: Iterable[PracticeResult]) -> dict[str, Any]:
    """Totales de un conjunto de resultados: de una sesión o de varias."""
    results = list(results)
    applied = [item for item in results if item.outcome in APPLIED]
    achieved = [item for item in applied if item.achieved]
    average = _average([item.seconds_to_achieve for item in achieved if item.seconds_to_achieve is not None])
    visible = sum(1 for item in applied if item.feedback_visible)
    return {
        "applied": len(applied),
        "achieved": len(achieved),
        "skipped": sum(1 for item in results if item.outcome is PracticeOutcome.SKIPPED),
        "stopped": sum(1 for item in results if item.outcome is PracticeOutcome.STOPPED),
        "average_seconds_to_achieve": average,
        "feedback_visible": visible,
        "sentence": practice_sentence(len(achieved), len(applied)),
        "average_sentence": average_sentence(average),
        "feedback_sentence": feedback_sentence(visible, len(applied)),
    }


def practice_by_target(results: Iterable[PracticeResult]) -> list[dict[str, Any]]:
    """Desglose por expresión pedida, en el orden del catálogo."""
    groups: dict[str, list[PracticeResult]] = {}
    for item in results:
        groups.setdefault(item.target_expression, []).append(item)
    rows = []
    for target in PRACTICE_TARGETS:
        if target in groups:
            totals = practice_totals(groups[target])
            rows.append({"target_expression": target, "applied": totals["applied"], "achieved": totals["achieved"],
                         "skipped": totals["skipped"], "stopped": totals["stopped"],
                         "average_seconds_to_achieve": totals["average_seconds_to_achieve"]})
    return rows


def practice_metrics(steps: Sequence[ProtocolStep], results: Iterable[PracticeResult]) -> dict[str, Any] | None:
    """Ejercicios de práctica de una sesión; None si el protocolo no tiene ninguno.
    Un ejercicio al que la sesión no llegó figura sin resultado."""
    practice_steps = [(index, step) for index, step in enumerate(steps) if step.is_practice]
    if not practice_steps:
        return None
    by_step = {item.step_index: item for item in results}
    exercises = []
    for index, step in practice_steps:
        item = by_step.get(index)
        exercises.append({
            "step_index": index, "target_expression": step.target_expression, "hold_seconds": step.hold_seconds,
            "max_seconds": step.exposure_seconds, "imitate": step.imitate,
            # None: la sesión no llegó a este ejercicio.
            "outcome": item.outcome.value if item else None,
            "seconds_to_achieve": item.seconds_to_achieve if item else None,
            "peak_level": item.peak_level if item else None,
            "relative_to_calibration": item.relative_to_calibration if item else None,
            "feedback_visible": item.feedback_visible if item else None,
        })
    found = [by_step[index] for index, _ in practice_steps if index in by_step]
    return {
        "exercises": exercises,
        "totals": {**practice_totals(found), "exercises": len(exercises),
                   "not_reached": sum(1 for item in exercises if item["outcome"] is None)},
        "by_target": practice_by_target(found),
        "notice": PRACTICE_NOTICE,
    }


# --- Reconocimiento de emociones ------------------------------------------------------------
# También aparte: aquí se compara la opción elegida con la expresión esperada de
# la imagen, no la expresión estimada del rostro. Un paso cuenta cuando llegó a
# su final (respondido o con el tiempo vencido, que figura sin respuesta).

ANSWERED_OR_TIMED_OUT = (RecognitionOutcome.ANSWERED, RecognitionOutcome.TIMED_OUT)


def recognition_sentence(matched: int, applied: int) -> str:
    if applied == 0:
        return "Ningún ejercicio de reconocimiento llegó a terminar."
    noun = "ejercicio" if applied == 1 else "ejercicios"
    return f"Eligió la emoción de la imagen en {matched} de {applied} {noun}."


def recognition_totals(results: Iterable[RecognitionResult]) -> dict[str, Any]:
    """Totales de un conjunto de resultados: de una sesión o de varias."""
    results = list(results)
    applied = [item for item in results if item.outcome in ANSWERED_OR_TIMED_OUT]
    matched = sum(1 for item in applied if item.matched)
    answered = [item for item in applied if item.outcome is RecognitionOutcome.ANSWERED]
    average = _average([item.seconds_to_answer for item in answered if item.seconds_to_answer is not None])
    return {
        "applied": len(applied),
        "matched": matched,
        "timed_out": len(applied) - len(answered),
        "skipped": sum(1 for item in results if item.outcome is RecognitionOutcome.SKIPPED),
        "stopped": sum(1 for item in results if item.outcome is RecognitionOutcome.STOPPED),
        "average_seconds_to_answer": average,
        "sentence": recognition_sentence(matched, len(applied)),
    }


def recognition_by_target(results: Iterable[RecognitionResult]) -> list[dict[str, Any]]:
    """Desglose por la emoción de la imagen, en el orden del catálogo, con las
    opciones que se eligieron en su lugar (contadas, sin interpretar)."""
    groups: dict[str, list[RecognitionResult]] = {}
    for item in results:
        groups.setdefault(item.target_expression, []).append(item)
    rows = []
    for target in EXPRESSION_KEYS:
        if target in groups:
            totals = recognition_totals(groups[target])
            chosen: dict[str, int] = {}
            for item in groups[target]:
                if item.chosen_expression is not None and item.chosen_expression != target:
                    chosen[item.chosen_expression] = chosen.get(item.chosen_expression, 0) + 1
            rows.append({"target_expression": target, "applied": totals["applied"], "matched": totals["matched"],
                         "timed_out": totals["timed_out"], "skipped": totals["skipped"], "stopped": totals["stopped"],
                         "other_choices": [{"expression": key, "count": chosen[key]}
                                           for key in EXPRESSION_KEYS if key in chosen]})
    return rows


def recognition_metrics(steps: Sequence[ProtocolStep],
                        results: Iterable[RecognitionResult]) -> dict[str, Any] | None:
    """Reconocimientos de una sesión; None si el protocolo no tiene ninguno.
    Un paso al que la sesión no llegó figura sin resultado."""
    recognition_steps = [(index, step) for index, step in enumerate(steps) if step.is_recognition]
    if not recognition_steps:
        return None
    by_step = {item.step_index: item for item in results}
    exercises = []
    for index, step in recognition_steps:
        item = by_step.get(index)
        exercises.append({
            "step_index": index, "stimulus_id": step.stimulus_id, "target_expression": step.target_expression,
            "max_seconds": step.exposure_seconds,
            # None: la sesión no llegó a este paso.
            "options": list(item.options) if item else None,
            "outcome": item.outcome.value if item else None,
            "chosen_expression": item.chosen_expression if item else None,
            "matched": item.matched if item else None,
            "seconds_to_answer": item.seconds_to_answer if item else None,
            "answered_by": item.answered_by.value if item and item.answered_by else None,
        })
    found = [by_step[index] for index, _ in recognition_steps if index in by_step]
    return {
        "exercises": exercises,
        "totals": {**recognition_totals(found), "exercises": len(exercises),
                   "not_reached": sum(1 for item in exercises if item["outcome"] is None)},
        "by_target": recognition_by_target(found),
        "notice": RECOGNITION_NOTICE,
    }
