from __future__ import annotations

from dataclasses import dataclass

from emotv.config import (
    ARMS_UP_ELBOW_TOLERANCE_DEGREES,
    ARMS_UP_WRIST_MARGIN,
    POSE_MIN_LANDMARK_VISIBILITY,
)
from emotv.domain.pose_landmarks import PoseLandmark, PoseLandmarks
from emotv.infrastructure.vision.movement_analysis.angle_calculator import (
    calculate_angle,
)


@dataclass(frozen=True, slots=True)
class ArmsUpThresholds:
    """Tolerancias geometricas para reconocer ambos brazos levantados."""

    min_visibility: float = POSE_MIN_LANDMARK_VISIBILITY
    wrist_above_shoulder_margin: float = ARMS_UP_WRIST_MARGIN
    elbow_straight_tolerance_degrees: float = ARMS_UP_ELBOW_TOLERANCE_DEGREES

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_visibility <= 1.0:
            raise ValueError("min_visibility debe estar entre 0 y 1")
        if self.wrist_above_shoulder_margin < 0.0:
            raise ValueError("wrist_above_shoulder_margin no puede ser negativo")
        if not 0.0 <= self.elbow_straight_tolerance_degrees <= 180.0:
            raise ValueError(
                "elbow_straight_tolerance_degrees debe estar entre 0 y 180"
            )


class PostureValidator:
    def __init__(self, thresholds: ArmsUpThresholds | None = None) -> None:
        self.thresholds = thresholds or ArmsUpThresholds()

    def both_arms_up(self, pose: PoseLandmarks) -> bool:
        """Valida altura, visibilidad y extension de ambos brazos."""

        upper_body = (
            pose.left_shoulder,
            pose.right_shoulder,
            pose.left_elbow,
            pose.right_elbow,
            pose.left_wrist,
            pose.right_wrist,
        )
        if not all(self._is_visible(landmark) for landmark in upper_body):
            return False

        margin = self.thresholds.wrist_above_shoulder_margin
        wrists_are_up = (
            pose.left_wrist.y <= pose.left_shoulder.y - margin
            and pose.right_wrist.y <= pose.right_shoulder.y - margin
        )
        if not wrists_are_up:
            return False

        minimum_elbow_angle = (
            180.0 - self.thresholds.elbow_straight_tolerance_degrees
        )
        left_elbow_angle = calculate_angle(
            pose.left_shoulder,
            pose.left_elbow,
            pose.left_wrist,
        )
        right_elbow_angle = calculate_angle(
            pose.right_shoulder,
            pose.right_elbow,
            pose.right_wrist,
        )

        return (
            left_elbow_angle >= minimum_elbow_angle
            and right_elbow_angle >= minimum_elbow_angle
        )

    def _is_visible(self, landmark: PoseLandmark) -> bool:
        return landmark.visibility >= self.thresholds.min_visibility
