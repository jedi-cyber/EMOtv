"""Registro de la expresión elegida en vivo: dominio, servicio, seguimiento y configuración."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from emotv.application import SessionService
from emotv.application.emotion_stabilizer import EmotionStabilizer
from emotv.application.live_expression import HOLD_LONGER, LOW_CONFIDENCE, NO_FACE, LiveExpressionTracker
from emotv.config import LiveExpressionSettings, get_live_expression_settings
from emotv.domain import (
    Activity, EmotionalActivityState, EmotionalActivityStatus, EmotionalSession,
    ExerciseState, ExerciseStatus, PostureId, SessionState, StabilizedEmotion,
)
from emotv.infrastructure.persistence import Base, PostgresSessionRepository, create_session_factory

T0 = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


@pytest.fixture
def service():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield SessionService(PostgresSessionRepository(create_session_factory(engine)), clock=Clock())
    engine.dispose()


def _recognized(service: SessionService) -> EmotionalSession:
    started = service.start_session()
    return service.record_recognition(started.id, "sadness", 0.8, "ferplus_onnx", "1.0")


def test_record_recognition_persists_state_and_timestamp(service):
    session = _recognized(service)
    stored = service.get_session(session.id)
    assert stored.state is SessionState.RECOGNIZED
    assert stored.recognized_at is not None and stored.recognized_at.tzinfo is not None
    assert (stored.initial_emotion, stored.emotion_confidence) == ("sadness", 0.8)
    assert (stored.emotion_model_id, stored.emotion_model_version) == ("ferplus_onnx", "1.0")


def test_only_one_recognition_per_session(service):
    session = _recognized(service)
    activity_started = service.assign_activity(session.id, "arms_up_5s")
    with pytest.raises(RuntimeError):
        service.record_recognition(activity_started.id, "happiness", 0.9, "ferplus_onnx", "1.0")


def test_recognition_rejects_other_registered_model(service):
    started = service.start_session()
    service.record_emotion_model(started.id, "ferplus_onnx", "1.0")
    with pytest.raises(ValueError):
        service.record_recognition(started.id, "sadness", 0.8, "hardlyhumans_vit", "rev")


def test_finish_without_activity_marks_skipped(service):
    finished = service.finish_without_activity(_recognized(service).id)
    assert finished.state is SessionState.COMPLETED
    assert finished.exercise_result == "skipped"
    assert finished.activity_id is None and finished.initial_emotion == "sadness"


def test_cancel_after_recognition_keeps_expression(service):
    for start_activity in (False, True):
        session = _recognized(service)
        if start_activity:
            session = service.assign_activity(session.id, "arms_up_5s")
        closed = service.cancel_session(session.id)
        assert closed.state is SessionState.COMPLETED
        assert closed.exercise_result == "cancelled"
        assert closed.initial_emotion == "sadness" and closed.recognized_at is not None


def test_cancel_without_recognition_still_cancels(service):
    cancelled = service.cancel_session(service.start_session().id)
    assert cancelled.state is SessionState.CANCELLED and cancelled.initial_emotion is None


def test_activity_completion_does_not_overwrite_recognition(service):
    session = service.assign_activity(_recognized(service).id, "arms_up_5s")
    activity = Activity("arms_up_5s", "Brazos arriba", "Eleva", PostureId.ARMS_UP, 5)
    status = EmotionalActivityStatus(
        EmotionalActivityState.COMPLETED, "Completada",
        StabilizedEmotion("happiness", 0.99, 1, 1, 1), activity,
        exercise=ExerciseStatus(ExerciseState.COMPLETED, 1, 5),
    )
    completed = service.complete_from_activity_status(session.id, status)
    assert completed.exercise_result == "completed"
    assert (completed.initial_emotion, completed.emotion_confidence) == ("sadness", 0.8)
    assert completed.recognized_at == session.recognized_at


def test_assign_activity_requires_recognition(service):
    with pytest.raises(RuntimeError):
        service.assign_activity(service.start_session().id, "arms_up_5s")


def test_domain_rules_for_recognition():
    with pytest.raises(ValueError):
        EmotionalSession("s", T0, SessionState.RECOGNIZED, initial_emotion="sadness", emotion_confidence=.8)
    with pytest.raises(ValueError):
        EmotionalSession("s", T0, SessionState.IN_PROGRESS, recognized_at=T0)
    with pytest.raises(ValueError):
        EmotionalSession("s", T0, SessionState.IN_PROGRESS, initial_emotion="sadness",
                         emotion_confidence=.8, recognized_at=T0 - timedelta(seconds=1))
    with pytest.raises(ValueError):
        EmotionalSession("s", T0, SessionState.COMPLETED, completed_at=T0, initial_emotion="sadness",
                         emotion_confidence=.8, exercise_result="completed")
    skipped = EmotionalSession("s", T0, SessionState.COMPLETED, completed_at=T0, initial_emotion="sadness",
                               emotion_confidence=.8, exercise_result="skipped", recognized_at=T0)
    assert skipped.activity_id is None


class FakeMonotonic:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _tracker(clock, **options):
    stabilizer = EmotionStabilizer(window_size=3, min_samples=2, min_confidence=0.0, min_agreement=0.6)
    return LiveExpressionTracker(stabilizer, stable_seconds=1.0, min_confidence=0.5, clock=clock, **options)


def test_tracker_requires_face_stability_and_confidence():
    clock = FakeMonotonic()
    tracker = _tracker(clock)
    assert tracker.update(None).blocked_reason == NO_FACE
    tracker.update(("happiness", .9))
    reading = tracker.update(("happiness", .9), {"happiness": .9, "neutral": .06, "sadness": .03, "fear": .01})
    assert reading.expression.emotion == "happiness"
    assert [label for label, _ in reading.top] == ["happiness", "neutral", "sadness"]
    assert reading.blocked_reason == HOLD_LONGER
    with pytest.raises(ValueError, match="momento"):
        tracker.confirm()
    clock.now += 1.0
    assert tracker.confirm().emotion == "happiness"


def test_tracker_restarts_hold_time_when_expression_changes_or_face_is_lost():
    clock = FakeMonotonic()
    tracker = _tracker(clock)
    tracker.update(("happiness", .9)); tracker.update(("happiness", .9))
    clock.now += 2.0
    tracker.update(("sadness", .9)); tracker.update(("sadness", .9)); tracker.update(("sadness", .9))
    assert tracker.update(("sadness", .9)).stable_seconds == 0.0
    clock.now += 1.0
    assert tracker.confirm().emotion == "sadness"
    tracker.update(None)
    with pytest.raises(ValueError, match="rostro"):
        tracker.confirm()


def test_tracker_rejects_low_confidence():
    clock = FakeMonotonic()
    tracker = _tracker(clock)
    tracker.update(("sadness", .3)); tracker.update(("sadness", .3))
    clock.now += 5
    with pytest.raises(ValueError) as error:
        tracker.confirm()
    assert str(error.value) == LOW_CONFIDENCE


def test_frame_analyzer_returns_distribution_when_classifier_offers_it():
    import numpy as np
    from emotv.infrastructure.vision.emotion_classifier.emotion_frame_analyzer import EmotionFrameAnalyzer

    class Detector:
        def detect(self, frame):
            return ["face"]

    class Preprocessor:
        def process(self, frame, detection):
            return type("Face", (), {"is_valid": True})()

    class PlainClassifier:
        def predict(self, face):
            return "neutral", .7

    class DistributionClassifier(PlainClassifier):
        def predict_distribution(self, face):
            return {"neutral": .2, "sadness": .7, "anger": .1}

    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    plain = EmotionFrameAnalyzer(Detector(), Preprocessor(), PlainClassifier())
    assert plain.analyze_detailed(frame) == (("neutral", .7), None)
    detailed = EmotionFrameAnalyzer(Detector(), Preprocessor(), DistributionClassifier())
    assert detailed.analyze_detailed(frame) == (("sadness", .7), {"neutral": .2, "sadness": .7, "anger": .1})


def test_live_settings_from_environment():
    assert get_live_expression_settings({}) == LiveExpressionSettings(1.0, 0.5)
    assert get_live_expression_settings({"LIVE_STABLE_SECONDS": "2.5", "LIVE_MIN_CONFIDENCE": "0.7"}) == \
        LiveExpressionSettings(2.5, 0.7)
    for name, value in (("LIVE_STABLE_SECONDS", "-1"), ("LIVE_MIN_CONFIDENCE", "1.5"), ("LIVE_STABLE_SECONDS", "x")):
        with pytest.raises(ValueError, match=name):
            get_live_expression_settings({name: value})
