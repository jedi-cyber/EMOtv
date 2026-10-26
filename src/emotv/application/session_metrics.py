"""Métricas descriptivas por estímulo de una sesión.

El sistema describe; no interpreta. Los textos dicen lo que ocurrió ("en 3 de 5
estímulos la expresión estimada coincidió con la esperada") y nunca valoran a la
persona. Las capturas de mala calidad se muestran, pero no cuentan en los
totales. Las imágenes abstractas no tienen métricas de coincidencia.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from emotv.domain.guided_session import ABSTRACT_NOTICE, CaptureQuality, ExpressionCapture, VerbalResponse
from emotv.domain.protocol import ProtocolStep
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
