"""Métricas descriptivas y tendencias con datos sintéticos (sin personas ni modelos)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re

from emotv.application.session_metrics import NOT_ENOUGH_SESSIONS, SessionPoint, stimulus_metrics, trend
from emotv.domain.guided_session import ABSTRACT_NOTICE, ExpressionCapture, VerbalResponse
from emotv.domain.protocol import ProtocolStep
from emotv.domain.stimulus import Stimulus

T0 = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
VALUATIONS = re.compile(r"(anormal|normal|mejor|peor|bien|mal|correct|incorrect|patol|riesgo|diagn|preocup)", re.I)


def stimulus(stimulus_id, expected=None, kind="emotional"):
    return Stimulus(id=stimulus_id, title=f"Estímulo {stimulus_id}", kind=kind, category="c", intensity="mild",
                    min_age=5, origin="Propio", license="Uso docente", scope="group", owner_user_id="d",
                    content_type="image/png", created_at=T0, expected_expression=expected if kind == "emotional" else None)


def capture(step, emotion, seconds, issues=(), confidence=0.7):
    return ExpressionCapture(
        id=f"c-{step}-{seconds}", session_id="s", captured_at=T0 + timedelta(seconds=10 * step + seconds),
        emotion_model_id="m", emotion_model_version="1", quality="flagged" if issues else "good", quality_issues=issues,
        step_index=step, stimulus_id=f"e{step}", seconds_since_stimulus=seconds, emotion=emotion,
        confidence=confidence if emotion else None)


def sample():
    expected = ["happiness", "sadness", "fear", "fear", "surprise"]
    steps = [ProtocolStep(f"e{index}", 6, 2) for index in range(5)] + [ProtocolStep("a1", 8, 2, True)]
    stimuli = {f"e{index}": stimulus(f"e{index}", value) for index, value in enumerate(expected)}
    stimuli["a1"] = stimulus("a1", kind="abstract")
    captures = [
        capture(0, "happiness", 2),                         # coincide
        capture(1, "happiness", 2, issues=("off_center",)),  # marcada: se muestra, no cuenta
        capture(1, "sadness", 4),                           # la primera buena decide: coincide
        capture(2, "fear", 2, issues=("too_dark",)),        # solo marcada: el estímulo no cuenta
        capture(3, "anger", 2),                             # no coincide
        # Estímulo 4 saltado, sin capturas.
        capture(5, "neutral", 2), capture(5, "surprise", 5),
    ]
    said = [VerbalResponse("v", "s", 5, "a1", "Una nube", T0, "u")]
    return stimulus_metrics(steps, stimuli, captures, said, skipped=[4])


def test_metrics_count_only_good_captures_and_describe_without_valuing():
    metrics = sample()
    assert metrics["totals"] == {"emotional_stimuli": 5, "counted": 3, "matched": 2, "excluded_captures": 2,
                                 "sentence": "En 2 de 3 estímulos la expresión estimada coincidió con la esperada."}
    by_step = {item["step_index"]: item for item in metrics["emotional"]}
    assert by_step[0]["matches_expected"] is True and by_step[1]["matches_expected"] is True
    assert by_step[3]["matches_expected"] is False
    # Las capturas marcadas se muestran con su problema, pero no cuentan.
    assert by_step[1]["captures"][0]["counted"] is False and by_step[1]["captures"][0]["quality_issues"] == ["off_center"]
    assert by_step[2]["counted"] is False and by_step[2]["matches_expected"] is None
    assert by_step[2]["captures"][0]["matches_expected"] is True  # se ve, aunque no cuenta
    assert by_step[4]["skipped"] is True and by_step[4]["captures"] == []
    assert by_step[0]["captures"][0]["probability"] == 0.7 and by_step[0]["captures"][0]["seconds_since_stimulus"] == 2
    assert not VALUATIONS.search(json.dumps(metrics, ensure_ascii=False))


def test_abstract_images_have_no_coincidence_metrics_and_always_the_notice():
    metrics = sample()
    abstract = metrics["abstract"]
    assert len(abstract) == 1 and abstract[0]["said"] == "Una nube" and len(abstract[0]["captures"]) == 2
    assert "matches_expected" not in json.dumps(abstract)
    assert "expected_expression" not in abstract[0] and "counted" not in abstract[0]
    assert metrics["abstract_notice"] == ABSTRACT_NOTICE
    assert stimulus_metrics([ProtocolStep("e0", 6, 2)], {"e0": stimulus("e0", "happiness")}, [])["abstract_notice"] is None


def test_no_good_capture_is_described_as_such():
    metrics = stimulus_metrics([ProtocolStep("e0", 6, 2)], {"e0": stimulus("e0", "happiness")},
                               [capture(0, None, 2, issues=("no_face",))])
    assert metrics["totals"]["counted"] == 0
    assert metrics["totals"]["sentence"] == "Ningún estímulo emocional tuvo una captura de buena calidad para comparar."


def test_a_single_session_is_not_drawn_as_a_trend():
    single = trend([SessionPoint("s1", "2026-10-01T10:00:00+00:00", 1, 3, 5)])
    assert single["comparable"] is False and single["message"] == NOT_ENOUGH_SESSIONS
    assert single["sessions"][0]["sentence"] == "En 3 de 5 estímulos la expresión estimada coincidió con la esperada."
    # Una sesión sin capturas válidas no es comparable.
    assert trend([SessionPoint("s1", "2026-10-01", 1, 3, 5), SessionPoint("s2", "2026-10-02", 1, 0, 0)])["comparable"] is False


def test_two_sessions_with_the_same_protocol_show_how_coincidences_change():
    result = trend([SessionPoint("s2", "2026-10-08T10:00:00+00:00", 2, 4, 5),
                    SessionPoint("s1", "2026-10-01T10:00:00+00:00", 1, 2, 5)])
    assert result["comparable"] is True
    assert [item["session_id"] for item in result["sessions"]] == ["s1", "s2"]
    assert result["message"] == ("En la primera sesión comparable coincidieron 2 de 5 estímulos; "
                                 "en la última, 4 de 5.")
    assert not VALUATIONS.search(json.dumps(result, ensure_ascii=False))
