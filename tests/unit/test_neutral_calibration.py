"""Calibración neutral en memoria: base promedio y mayor aumento respecto a ella."""
import pytest

from emotv.application.emotion_stabilizer import EmotionStabilizer
from emotv.application.live_expression import LiveExpressionTracker
from emotv.application.neutral_calibration import CALIBRATION_FAILED, NeutralCalibration


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


RELAXED = {"neutral": .80, "happiness": .05, "sadness": .15}


def _calibrated(clock, frames=5, **options):
    calibration = NeutralCalibration(seconds=3.0, clock=clock, **options)
    calibration.start()
    for _ in range(frames):
        assert calibration.add(RELAXED) is None
        clock.now += 0.75
    assert calibration.add(RELAXED) is None
    return calibration


def test_largest_increase_wins_even_if_it_is_not_the_most_likely_class():
    calibration = _calibrated(Clock())
    assert calibration.state == "calibrated"
    classes, suggested = calibration.compare({"neutral": .55, "happiness": .30, "sadness": .15})
    assert classes[0].emotion == "neutral"  # sigue siendo la más probable
    assert suggested == "happiness"         # pero es la que más aumentó
    by_label = {item.emotion: item for item in classes}
    assert by_label["happiness"].baseline == pytest.approx(.05)
    assert by_label["happiness"].change == pytest.approx(.25)
    assert by_label["neutral"].change == pytest.approx(-.25)


def test_no_suggestion_below_the_configured_minimum_increase():
    calibration = _calibrated(Clock(), min_increase=0.20)
    _, suggested = calibration.compare({"neutral": .70, "happiness": .20, "sadness": .10})
    assert suggested is None  # happiness solo sube 15 puntos


def test_frames_without_face_do_not_count_and_too_few_fail():
    clock = Clock()
    calibration = NeutralCalibration(seconds=3.0, min_samples=5, clock=clock)
    calibration.start()
    calibration.add(RELAXED)
    for _ in range(3):
        clock.now += 1.0
        notice = calibration.add(None)
    assert notice == CALIBRATION_FAILED
    assert calibration.state == "none"
    with pytest.raises(ValueError):
        calibration.compare(RELAXED)


def test_recalibration_discards_previous_baseline():
    clock = Clock()
    calibration = _calibrated(clock)
    calibration.start()
    assert calibration.state == "calibrating" and calibration.progress == 0.0
    with pytest.raises(ValueError):
        calibration.compare(RELAXED)


def test_tracker_reports_all_classes_sorted_and_the_calibrated_comparison():
    clock = Clock()
    tracker = LiveExpressionTracker(
        EmotionStabilizer(window_size=3, min_samples=2, min_confidence=0.0, min_agreement=0.6),
        clock=clock, calibration=NeutralCalibration(seconds=3.0, clock=clock),
    )
    eight = {"neutral": .5, "happiness": .2, "surprise": .1, "sadness": .08, "anger": .05,
             "disgust": .03, "fear": .02, "contempt": .02}
    reading = tracker.update(("neutral", .5), eight)
    assert [label for label, _ in reading.distribution] == list(eight)
    assert reading.calibration_state == "none" and reading.calibrated == ()

    tracker.start_calibration()
    for _ in range(5):
        reading = tracker.update(("neutral", .8), RELAXED)
        assert reading.calibration_state == "calibrating"
        clock.now += 0.7
    assert tracker.update(("neutral", .8), RELAXED).calibration_state == "calibrated"
    reading = tracker.update(("neutral", .55), {"neutral": .55, "happiness": .30, "sadness": .15})
    assert reading.calibration_state == "calibrated"
    assert reading.suggested == "happiness"
    # Lo registrable sigue siendo la lectura directa del modelo.
    assert reading.expression.emotion == "neutral"
