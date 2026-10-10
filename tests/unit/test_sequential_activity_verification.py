"""Verificación estricta de pasos y repeticiones con secuencias sintéticas de landmarks."""
from dataclasses import replace

import numpy as np
import pytest

from emotv.application.browser_activity_service import NO_BODY_MESSAGE, BrowserActivityService
from emotv.application.exercise_service import ExerciseService
from emotv.application.pose_service import PoseService
from emotv.application.session_service import SessionService
from emotv.config import ARMS_OPEN_WRIST_HEIGHT_TOLERANCE, ARMS_UP_WRIST_MARGIN
from emotv.domain import Activity, EmotionalActivityState, PoseResult, PostureId, StabilizedEmotion
from emotv.domain.activity import ActivityStep
from emotv.domain.session_state import SessionState
from emotv.infrastructure.persistence.in_memory_session_repository import InMemorySessionRepository
from emotv.infrastructure.vision.movement_analysis import PostureValidator
from tests.unit.test_multiple_postures import arms_open_pose, base_pose, hands_on_hips_pose
from tests.unit.test_new_sequence_postures import arms_forward_pose, squat_pose
from tests.unit.test_pose_foundation import make_pose

FRAME = np.zeros((8, 8, 3), dtype=np.uint8)
EMOTION = StabilizedEmotion("neutral", 0.9, 1.0, 1, 1)
TOLERANCE = 0.75

POSES = {
    PostureId.ARMS_UP: make_pose(wrists_y=0.2),
    PostureId.ARMS_OPEN: arms_open_pose(),
    PostureId.HANDS_ON_HIPS: hands_on_hips_pose(),
    PostureId.ARMS_FORWARD: arms_forward_pose(),
    PostureId.SQUAT: squat_pose(),
}


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class Detector:
    """Devuelve la pose programada; ``None`` simula un frame sin persona."""

    def __init__(self) -> None:
        self.pose = None

    def detect(self, frame):
        if self.pose is None:
            return PoseResult(detected=False)
        return PoseResult(detected=True, landmarks=self.pose)


def three_steps(repetitions: int = 1) -> Activity:
    return Activity(
        "flow", "Secuencia", "Tres pasos", PostureId.ARMS_UP, 2.0, repetitions=repetitions,
        steps=(
            ActivityStep(PostureId.ARMS_UP, "Brazos arriba", 2),
            ActivityStep(PostureId.ARMS_OPEN, "Brazos abiertos", 2),
            ActivityStep(PostureId.HANDS_ON_HIPS, "Manos en las caderas", 2),
        ),
    )


def make_service(activity: Activity):
    clock, detector = Clock(), Detector()
    service = BrowserActivityService(
        activity, object(), PoseService(detector=detector),
        exercise_service=ExerciseService(activity.steps[0].duration_seconds, clock, TOLERANCE),
        initial_emotion=EMOTION,
    )
    return service, clock, detector


def frame(service, clock, detector, pose, advance=0.0):
    clock.value += advance
    detector.pose = pose
    return service.process_frame(FRAME)


def test_sustained_correct_posture_completes_the_step():
    service, clock, detector = make_service(three_steps())
    pose = POSES[PostureId.ARMS_UP]

    first = frame(service, clock, detector, pose)
    halfway = frame(service, clock, detector, pose, 1.0)
    done = frame(service, clock, detector, pose, 1.0)

    assert first.state is EmotionalActivityState.PERFORMING_EXERCISE
    assert halfway.step_elapsed_seconds == pytest.approx(1.0)
    assert halfway.step_remaining_seconds == pytest.approx(1.0)
    assert halfway.exercise.progress == 0.0  # global: aún no hay pasos completados
    assert done.steps_completed == 1 and done.step_index == 1
    assert done.message.startswith("Siguiente postura")
    assert done.exercise.progress == pytest.approx(1 / 3)


def test_posture_of_another_step_never_advances():
    service, clock, detector = make_service(three_steps())
    # El paso actual es arms_up; arms_open es válida, pero para el paso siguiente.
    statuses = [frame(service, clock, detector, POSES[PostureId.ARMS_OPEN], 0.5) for _ in range(10)]

    assert all(status.step_index == 0 and status.steps_completed == 0 for status in statuses)
    assert all(status.step_elapsed_seconds == 0.0 for status in statuses)
    assert all(status.state is EmotionalActivityState.WAITING_FOR_POSTURE for status in statuses)


def test_brief_loss_of_landmarks_is_tolerated_without_counting_the_gap():
    service, clock, detector = make_service(three_steps())
    pose = POSES[PostureId.ARMS_UP]
    frame(service, clock, detector, pose)
    frame(service, clock, detector, pose, 1.0)

    blink = frame(service, clock, detector, None, 0.25)
    resumed = frame(service, clock, detector, pose, 0.25)
    after = frame(service, clock, detector, pose, 0.5)

    assert blink.step_elapsed_seconds == pytest.approx(1.0)  # congelado, no reiniciado
    assert blink.message == NO_BODY_MESSAGE
    assert resumed.step_elapsed_seconds == pytest.approx(1.0)  # el hueco no cuenta
    assert after.step_elapsed_seconds == pytest.approx(1.5)
    assert after.steps_completed == 0


def test_long_loss_of_landmarks_resets_the_step_counter():
    service, clock, detector = make_service(three_steps())
    pose = POSES[PostureId.ARMS_UP]
    frame(service, clock, detector, pose)
    frame(service, clock, detector, pose, 1.5)

    frame(service, clock, detector, None, 0.25)
    lost = frame(service, clock, detector, None, 1.0)  # 1.25 s > tolerancia
    back = frame(service, clock, detector, pose, 0.25)

    assert lost.step_elapsed_seconds == 0.0
    assert lost.state is EmotionalActivityState.WAITING_FOR_POSTURE
    assert back.step_elapsed_seconds == 0.0
    assert back.step_index == 0


def test_incorrect_visible_posture_resets_immediately():
    service, clock, detector = make_service(three_steps())
    frame(service, clock, detector, POSES[PostureId.ARMS_UP])
    frame(service, clock, detector, POSES[PostureId.ARMS_UP], 1.5)

    wrong = frame(service, clock, detector, base_pose(), 0.1)

    assert wrong.step_elapsed_seconds == 0.0


def test_low_visibility_does_not_advance_and_asks_to_step_back():
    service, clock, detector = make_service(three_steps())
    pose = POSES[PostureId.ARMS_UP]
    hidden = replace(pose, left_wrist=replace(pose.left_wrist, visibility=0.1))

    statuses = [frame(service, clock, detector, hidden, 0.5) for _ in range(6)]

    assert all(status.step_elapsed_seconds == 0.0 for status in statuses)
    assert all(status.steps_completed == 0 for status in statuses)
    assert "Aléjate" in statuses[-1].message and "céntrate" in statuses[-1].message
    assert statuses[-1].posture is not None and not statuses[-1].posture.landmarks_visible


def test_three_steps_times_two_repetitions_completes_exactly_six_steps():
    activity = three_steps(repetitions=2)
    service, clock, detector = make_service(activity)
    seen = []
    status = None

    for _ in range(20):  # más frames de los necesarios: no debe pasar de 6
        step = service.current_step
        before = (service.finished, step.posture)
        start = frame(service, clock, detector, POSES[step.posture])
        if start.completed:
            break
        seen.append((start.step_index, start.repetition_index, before[1]))
        status = frame(service, clock, detector, POSES[step.posture], step.duration_seconds)
        assert status.exercise.progress == pytest.approx(status.steps_completed / 6)
        if status.completed:
            break

    assert status is not None and status.completed
    assert status.steps_completed == 6 and status.step_count == 6
    assert status.repetition_count == 2
    assert status.exercise.progress == 1.0
    assert status.exercise.elapsed_seconds == pytest.approx(12.0)
    assert [(index, repetition) for index, repetition, _ in seen] == [
        (0, 0), (1, 0), (2, 0), (3, 1), (4, 1), (5, 1),
    ]
    assert [posture for *_, posture in seen] == [step.posture for step in activity.steps] * 2
    extra = frame(service, clock, detector, POSES[PostureId.ARMS_UP], 5.0)
    assert extra.completed and extra.steps_completed == 6


@pytest.mark.parametrize("posture", list(PostureId))
def test_each_canonical_pose_is_accepted_only_by_its_own_validator(posture):
    validator = PostureValidator()
    accepted = {
        candidate for candidate in PostureId
        if validator.validate(POSES[posture], candidate).detected
    }
    assert accepted == {posture}


def test_arms_up_margin_excludes_arms_open_height_band():
    assert ARMS_UP_WRIST_MARGIN > ARMS_OPEN_WRIST_HEIGHT_TOLERANCE
    # Brazos extendidos a los lados, apenas por encima de los hombros.
    raised = arms_open_pose()
    raised = replace(raised, **{
        name: replace(getattr(raised, name), y=0.25)
        for name in ("left_elbow", "right_elbow", "left_wrist", "right_wrist")
    })
    validator = PostureValidator()

    assert validator.validate(raised, PostureId.ARMS_OPEN).detected
    assert not validator.validate(raised, PostureId.ARMS_UP).detected


def test_progress_is_persisted_and_survives_interruption():
    repository = InMemorySessionRepository()
    sessions = SessionService(repository)
    session = sessions.start_session(activity_id="flow")
    service, clock, detector = make_service(three_steps(repetitions=2))
    pose = POSES[PostureId.ARMS_UP]
    frame(service, clock, detector, pose)
    after_first = frame(service, clock, detector, pose, 2.0)

    sessions.record_activity_progress(session.id, after_first)
    cancelled = sessions.cancel_session(session.id)

    assert cancelled.state is SessionState.CANCELLED
    assert (cancelled.exercise_steps_completed, cancelled.exercise_steps_total,
            cancelled.exercise_repetitions) == (1, 6, 2)
    assert cancelled.exercise_duration_seconds == pytest.approx(2.0)


def test_completion_persists_steps_repetitions_and_duration():
    sessions = SessionService(InMemorySessionRepository())
    session = sessions.start_session(activity_id="flow")
    service, clock, detector = make_service(three_steps(repetitions=2))
    status = None
    while status is None or not status.completed:
        step = service.current_step
        frame(service, clock, detector, POSES[step.posture])
        status = frame(service, clock, detector, POSES[step.posture], step.duration_seconds)

    stored = sessions.complete_from_activity_status(session.id, status)

    assert stored.exercise_result == "completed"
    assert (stored.exercise_steps_completed, stored.exercise_steps_total,
            stored.exercise_repetitions) == (6, 6, 2)
    assert stored.exercise_duration_seconds == pytest.approx(12.0)
