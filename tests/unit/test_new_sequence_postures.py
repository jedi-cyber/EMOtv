from dataclasses import replace

import pytest
import numpy as np

from emotv.application.activity_catalog import DEFAULT_ACTIVITIES
from emotv.application.browser_activity_service import BrowserActivityService
from emotv.application.exercise_service import ExerciseService
from emotv.application.pose_service import PoseService
from emotv.domain import PoseLandmark, PoseResult, PostureId, StabilizedEmotion
from emotv.infrastructure.vision.movement_analysis import (
    ArmsForwardThresholds,
    PostureValidator,
    SquatThresholds,
)
from tests.unit.test_multiple_postures import (
    arms_open_pose, base_pose, hands_on_hips_pose,
)
from tests.unit.test_pose_foundation import make_pose


def arms_forward_pose():
    return replace(
        base_pose(),
        left_elbow=PoseLandmark(0.35, 0.3, z=-0.18),
        right_elbow=PoseLandmark(0.65, 0.3, z=-0.18),
        left_wrist=PoseLandmark(0.35, 0.3, z=-0.36),
        right_wrist=PoseLandmark(0.65, 0.3, z=-0.36),
    )


def squat_pose():
    return replace(
        base_pose(),
        left_hip=PoseLandmark(0.4, 0.56, z=0.03),
        right_hip=PoseLandmark(0.6, 0.56, z=0.03),
        left_knee=PoseLandmark(0.4, 0.76, z=-0.12),
        right_knee=PoseLandmark(0.6, 0.76, z=-0.12),
        left_ankle=PoseLandmark(0.4, 0.96, z=0.03),
        right_ankle=PoseLandmark(0.6, 0.96, z=0.03),
    )


def test_every_catalog_step_has_a_registered_validator():
    supported = PostureValidator().supported_postures
    assert supported == set(PostureId)
    assert all(step.posture in supported for activity in DEFAULT_ACTIVITIES for step in activity.steps)


def test_detects_both_arms_forward():
    result = PostureValidator().validate(arms_forward_pose(), PostureId.ARMS_FORWARD)
    assert result.detected
    assert result.confidence == 1
    assert result.measurements["left_elbow_angle"] == pytest.approx(180)


@pytest.mark.parametrize("field,rule", [
    ("left_wrist", "left_wrist_forward"),
    ("right_elbow", "right_elbow_forward"),
])
def test_arms_forward_requires_depth(field, rule):
    pose = arms_forward_pose()
    pose = replace(pose, **{field: replace(getattr(pose, field), z=0)})
    assert rule in PostureValidator().validate(pose, PostureId.ARMS_FORWARD).failed_rules


def test_arms_forward_rejects_bent_elbow():
    pose = arms_forward_pose()
    pose = replace(pose, left_wrist=replace(pose.left_wrist, x=0.58))
    assert "left_elbow_extended" in PostureValidator().validate(pose, "arms_forward").failed_rules


def test_arms_forward_rejects_low_visibility_or_wrong_height():
    pose = arms_forward_pose()
    pose = replace(pose, left_wrist=replace(pose.left_wrist, visibility=0.1, y=0.55))
    failed = PostureValidator().validate(pose, "arms_forward").failed_rules
    assert "upper_body_visible" in failed
    assert "left_wrist_at_shoulder_height" in failed


def test_arms_forward_thresholds_are_configurable():
    pose = arms_forward_pose()
    validator = PostureValidator(arms_forward_thresholds=ArmsForwardThresholds(min_wrist_depth=0.4))
    assert not validator.validate(pose, "arms_forward").detected
    with pytest.raises(ValueError):
        ArmsForwardThresholds(min_wrist_depth=-1)


def test_detects_squat():
    result = PostureValidator().validate(squat_pose(), PostureId.SQUAT)
    assert result.detected
    assert 65 <= result.measurements["left_knee_angle"] <= 155


def test_squat_rejects_straight_legs():
    result = PostureValidator().validate(base_pose(), PostureId.SQUAT)
    assert not result.detected
    assert "left_knee_bent" in result.failed_rules
    assert "right_knee_bent" in result.failed_rules


def test_squat_requires_both_knees_bent():
    pose = squat_pose()
    pose = replace(pose, right_knee=replace(pose.right_knee, z=0.03))
    assert "right_knee_bent" in PostureValidator().validate(pose, "squat").failed_rules


def test_squat_requires_visible_ordered_body():
    pose = squat_pose()
    pose = replace(pose, left_ankle=replace(pose.left_ankle, visibility=0.1),
                   right_hip=replace(pose.right_hip, y=0.86))
    failed = PostureValidator().validate(pose, "squat").failed_rules
    assert "body_visible" in failed
    assert "right_hip_above_knee" in failed


def test_squat_thresholds_are_configurable():
    pose = squat_pose()
    validator = PostureValidator(squat_thresholds=SquatThresholds(max_knee_angle=90))
    assert not validator.validate(pose, "squat").detected
    with pytest.raises(ValueError):
        SquatThresholds(min_knee_angle=160, max_knee_angle=150)


def test_every_default_activity_can_finish_with_real_geometry():
    poses = {
        PostureId.ARMS_UP: make_pose(wrists_y=0.2),
        PostureId.ARMS_OPEN: arms_open_pose(),
        PostureId.HANDS_ON_HIPS: hands_on_hips_pose(),
        PostureId.ARMS_FORWARD: arms_forward_pose(),
        PostureId.SQUAT: squat_pose(),
    }

    class Clock:
        value = 0.0

        def __call__(self):
            return self.value

    class Detector:
        pose = None

        def detect(self, frame):
            return PoseResult(detected=True, landmarks=self.pose)

    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    for activity in DEFAULT_ACTIVITIES:
        clock = Clock()
        detector = Detector()
        service = BrowserActivityService(
            activity, object(), PoseService(detector=detector),
            exercise_service=ExerciseService(activity.steps[0].duration_seconds, clock),
            initial_emotion=StabilizedEmotion("neutral", 0.9, 1.0, 1, 1),
        )
        for step in activity.steps * activity.repetitions:
            detector.pose = poses[step.posture]
            holding = service.process_frame(frame)
            assert holding.posture is not None and holding.posture.detected, (activity.id, step.posture)
            clock.value += step.duration_seconds
            status = service.process_frame(frame)
        assert status.completed and status.exercise.progress == 1.0, activity.id
