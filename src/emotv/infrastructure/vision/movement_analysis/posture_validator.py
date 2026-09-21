from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from emotv.config import (
    ARMS_OPEN_ELBOW_TOLERANCE_DEGREES,
    ARMS_OPEN_LATERAL_MARGIN,
    ARMS_OPEN_WRIST_HEIGHT_TOLERANCE,
    ARMS_FORWARD_ELBOW_TOLERANCE_DEGREES,
    ARMS_FORWARD_MIN_ELBOW_DEPTH,
    ARMS_FORWARD_MIN_WRIST_DEPTH,
    ARMS_FORWARD_MIN_WRIST_ELBOW_DEPTH,
    ARMS_FORWARD_WRIST_HEIGHT_TOLERANCE,
    ARMS_FORWARD_WRIST_LATERAL_TOLERANCE,
    ARMS_UP_ELBOW_TOLERANCE_DEGREES,
    ARMS_UP_WRIST_MARGIN,
    HANDS_ON_HIPS_DISTANCE_TOLERANCE,
    HANDS_ON_HIPS_ELBOW_OUTWARD_MARGIN,
    HANDS_ON_HIPS_MAX_ELBOW_ANGLE,
    HANDS_ON_HIPS_MIN_ELBOW_ANGLE,
    POSE_MIN_LANDMARK_VISIBILITY,
    SQUAT_MAX_KNEE_ANGLE,
    SQUAT_MIN_HIP_KNEE_GAP,
    SQUAT_MIN_KNEE_ANGLE,
    SQUAT_MIN_KNEE_ANKLE_GAP,
    SQUAT_MIN_SHOULDER_HIP_GAP,
)
from emotv.domain.pose_landmarks import PoseLandmark, PoseLandmarks
from emotv.domain.posture_id import PostureId
from emotv.domain.posture_result import PostureResult
from emotv.infrastructure.vision.movement_analysis.angle_calculator import (
    calculate_angle,
    calculate_3d_angle,
)


PostureEvaluator = Callable[[PoseLandmarks], PostureResult]


@dataclass(frozen=True, slots=True)
class ArmsUpThresholds:
    """Tolerancias geométricas para reconocer ambos brazos levantados."""

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


@dataclass(frozen=True, slots=True)
class ArmsOpenThresholds:
    min_visibility: float = POSE_MIN_LANDMARK_VISIBILITY
    wrist_height_tolerance: float = ARMS_OPEN_WRIST_HEIGHT_TOLERANCE
    lateral_margin: float = ARMS_OPEN_LATERAL_MARGIN
    elbow_straight_tolerance_degrees: float = ARMS_OPEN_ELBOW_TOLERANCE_DEGREES

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_visibility <= 1.0:
            raise ValueError("min_visibility debe estar entre 0 y 1")
        if self.wrist_height_tolerance < 0.0 or self.lateral_margin < 0.0:
            raise ValueError("Las tolerancias espaciales no pueden ser negativas")
        if not 0.0 <= self.elbow_straight_tolerance_degrees <= 180.0:
            raise ValueError(
                "elbow_straight_tolerance_degrees debe estar entre 0 y 180"
            )


@dataclass(frozen=True, slots=True)
class HandsOnHipsThresholds:
    min_visibility: float = POSE_MIN_LANDMARK_VISIBILITY
    wrist_hip_distance_tolerance: float = HANDS_ON_HIPS_DISTANCE_TOLERANCE
    min_elbow_angle: float = HANDS_ON_HIPS_MIN_ELBOW_ANGLE
    max_elbow_angle: float = HANDS_ON_HIPS_MAX_ELBOW_ANGLE
    elbow_outward_margin: float = HANDS_ON_HIPS_ELBOW_OUTWARD_MARGIN

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_visibility <= 1.0:
            raise ValueError("min_visibility debe estar entre 0 y 1")
        if self.wrist_hip_distance_tolerance < 0.0:
            raise ValueError("wrist_hip_distance_tolerance no puede ser negativa")
        if self.elbow_outward_margin < 0.0:
            raise ValueError("elbow_outward_margin no puede ser negativo")
        if not 0.0 <= self.min_elbow_angle <= self.max_elbow_angle <= 180.0:
            raise ValueError("El rango de ángulos de codo no es válido")


@dataclass(frozen=True, slots=True)
class ArmsForwardThresholds:
    min_visibility: float = POSE_MIN_LANDMARK_VISIBILITY
    min_wrist_depth: float = ARMS_FORWARD_MIN_WRIST_DEPTH
    min_elbow_depth: float = ARMS_FORWARD_MIN_ELBOW_DEPTH
    min_wrist_elbow_depth: float = ARMS_FORWARD_MIN_WRIST_ELBOW_DEPTH
    wrist_height_tolerance: float = ARMS_FORWARD_WRIST_HEIGHT_TOLERANCE
    wrist_lateral_tolerance: float = ARMS_FORWARD_WRIST_LATERAL_TOLERANCE
    elbow_straight_tolerance_degrees: float = ARMS_FORWARD_ELBOW_TOLERANCE_DEGREES

    def __post_init__(self) -> None:
        if not 0 <= self.min_visibility <= 1:
            raise ValueError("min_visibility debe estar entre 0 y 1")
        if any(value < 0 for value in (
            self.min_wrist_depth, self.min_elbow_depth,
            self.min_wrist_elbow_depth, self.wrist_height_tolerance,
            self.wrist_lateral_tolerance,
        )):
            raise ValueError("Las tolerancias espaciales no pueden ser negativas")
        if not 0 <= self.elbow_straight_tolerance_degrees <= 180:
            raise ValueError("La tolerancia de codo debe estar entre 0 y 180")


@dataclass(frozen=True, slots=True)
class SquatThresholds:
    min_visibility: float = POSE_MIN_LANDMARK_VISIBILITY
    min_knee_angle: float = SQUAT_MIN_KNEE_ANGLE
    max_knee_angle: float = SQUAT_MAX_KNEE_ANGLE
    min_shoulder_hip_gap: float = SQUAT_MIN_SHOULDER_HIP_GAP
    min_hip_knee_gap: float = SQUAT_MIN_HIP_KNEE_GAP
    min_knee_ankle_gap: float = SQUAT_MIN_KNEE_ANKLE_GAP

    def __post_init__(self) -> None:
        if not 0 <= self.min_visibility <= 1:
            raise ValueError("min_visibility debe estar entre 0 y 1")
        if not 0 <= self.min_knee_angle <= self.max_knee_angle <= 180:
            raise ValueError("El rango de ángulos de rodilla no es válido")
        if any(value < 0 for value in (
            self.min_shoulder_hip_gap, self.min_hip_knee_gap,
            self.min_knee_ankle_gap,
        )):
            raise ValueError("Las separaciones verticales no pueden ser negativas")


class PostureValidator:
    """Selecciona y ejecuta validadores de postura registrados."""

    def __init__(
        self,
        thresholds: ArmsUpThresholds | None = None,
        arms_open_thresholds: ArmsOpenThresholds | None = None,
        hands_on_hips_thresholds: HandsOnHipsThresholds | None = None,
        arms_forward_thresholds: ArmsForwardThresholds | None = None,
        squat_thresholds: SquatThresholds | None = None,
    ) -> None:
        self.thresholds = thresholds or ArmsUpThresholds()
        self.arms_open_thresholds = arms_open_thresholds or ArmsOpenThresholds()
        self.hands_on_hips_thresholds = (
            hands_on_hips_thresholds or HandsOnHipsThresholds()
        )
        self.arms_forward_thresholds = arms_forward_thresholds or ArmsForwardThresholds()
        self.squat_thresholds = squat_thresholds or SquatThresholds()
        self._evaluators: dict[PostureId, PostureEvaluator] = {
            PostureId.ARMS_UP: self._evaluate_arms_up,
            PostureId.ARMS_OPEN: self._evaluate_arms_open,
            PostureId.HANDS_ON_HIPS: self._evaluate_hands_on_hips,
            PostureId.ARMS_FORWARD: self._evaluate_arms_forward,
            PostureId.SQUAT: self._evaluate_squat,
        }

    @property
    def supported_postures(self) -> frozenset[PostureId]:
        return frozenset(self._evaluators)

    def register(
        self,
        posture_id: PostureId | str,
        evaluator: PostureEvaluator,
        *,
        replace: bool = False,
    ) -> None:
        """Registra un evaluador adicional sin modificar el despachador."""

        normalized_id = PostureId(posture_id)
        if normalized_id in self._evaluators and not replace:
            raise ValueError(f"La postura {normalized_id.value} ya está registrada")
        self._evaluators[normalized_id] = evaluator

    def validate(
        self,
        pose: PoseLandmarks,
        posture_id: PostureId | str,
    ) -> PostureResult:
        """Evalúa una pose usando el validador asociado al identificador."""

        normalized_id = PostureId(posture_id)
        evaluator = self._evaluators.get(normalized_id)
        if evaluator is None:
            raise NotImplementedError(
                f"La postura {normalized_id.value} aún no tiene un validador"
            )

        result = evaluator(pose)
        if result.posture_id is not normalized_id:
            raise ValueError(
                "El evaluador devolvió un PostureResult para otra postura"
            )
        return result

    def both_arms_up(self, pose: PoseLandmarks) -> bool:
        """API compatible: delega en el evaluador genérico de ``arms_up``."""

        return self.validate(pose, PostureId.ARMS_UP).detected

    def _evaluate_arms_up(self, pose: PoseLandmarks) -> PostureResult:
        upper_body = (
            pose.left_shoulder,
            pose.right_shoulder,
            pose.left_elbow,
            pose.right_elbow,
            pose.left_wrist,
            pose.right_wrist,
        )
        minimum_visibility = min(point.visibility for point in upper_body)
        left_wrist_offset = pose.left_shoulder.y - pose.left_wrist.y
        right_wrist_offset = pose.right_shoulder.y - pose.right_wrist.y
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

        margin = self.thresholds.wrist_above_shoulder_margin
        minimum_angle = (
            180.0 - self.thresholds.elbow_straight_tolerance_degrees
        )
        rules = {
            "upper_body_visible": all(self._is_visible(point) for point in upper_body),
            "left_wrist_above_shoulder": left_wrist_offset >= margin,
            "right_wrist_above_shoulder": right_wrist_offset >= margin,
            "left_elbow_extended": left_elbow_angle >= minimum_angle,
            "right_elbow_extended": right_elbow_angle >= minimum_angle,
        }
        failed_rules = tuple(name for name, passed in rules.items() if not passed)
        confidence = sum(rules.values()) / len(rules)
        detected = not failed_rules

        return PostureResult(
            posture_id=PostureId.ARMS_UP,
            detected=detected,
            confidence=confidence,
            message=(
                "Postura correcta"
                if detected
                else "Ajusta la visibilidad, altura o extensión de los brazos"
            ),
            measurements={
                "minimum_visibility": minimum_visibility,
                "left_wrist_offset": left_wrist_offset,
                "right_wrist_offset": right_wrist_offset,
                "left_elbow_angle": left_elbow_angle,
                "right_elbow_angle": right_elbow_angle,
            },
            failed_rules=failed_rules,
        )

    def _evaluate_arms_open(self, pose: PoseLandmarks) -> PostureResult:
        thresholds = self.arms_open_thresholds
        upper_body = (
            pose.left_shoulder,
            pose.right_shoulder,
            pose.left_elbow,
            pose.right_elbow,
            pose.left_wrist,
            pose.right_wrist,
        )
        left_height_delta = abs(pose.left_wrist.y - pose.left_shoulder.y)
        right_height_delta = abs(pose.right_wrist.y - pose.right_shoulder.y)
        left_lateral_offset = self._outward_offset(
            pose.left_wrist,
            pose.left_shoulder,
            pose,
        )
        right_lateral_offset = self._outward_offset(
            pose.right_wrist,
            pose.right_shoulder,
            pose,
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
        minimum_angle = 180.0 - thresholds.elbow_straight_tolerance_degrees

        rules = {
            "upper_body_visible": all(
                self._is_visible(point, thresholds.min_visibility)
                for point in upper_body
            ),
            "left_wrist_at_shoulder_height": (
                left_height_delta <= thresholds.wrist_height_tolerance
            ),
            "right_wrist_at_shoulder_height": (
                right_height_delta <= thresholds.wrist_height_tolerance
            ),
            "left_arm_open_laterally": left_lateral_offset >= thresholds.lateral_margin,
            "right_arm_open_laterally": (
                right_lateral_offset >= thresholds.lateral_margin
            ),
            "left_elbow_extended": left_elbow_angle >= minimum_angle,
            "right_elbow_extended": right_elbow_angle >= minimum_angle,
        }
        return self._build_result(
            posture_id=PostureId.ARMS_OPEN,
            rules=rules,
            measurements={
                "minimum_visibility": min(point.visibility for point in upper_body),
                "left_wrist_height_delta": left_height_delta,
                "right_wrist_height_delta": right_height_delta,
                "left_lateral_offset": left_lateral_offset,
                "right_lateral_offset": right_lateral_offset,
                "left_elbow_angle": left_elbow_angle,
                "right_elbow_angle": right_elbow_angle,
            },
            success_message="Postura de brazos abiertos correcta",
            failure_message="Alinea y extiende ambos brazos hacia los lados",
        )

    def _evaluate_hands_on_hips(self, pose: PoseLandmarks) -> PostureResult:
        thresholds = self.hands_on_hips_thresholds
        relevant_points = (
            pose.left_shoulder,
            pose.right_shoulder,
            pose.left_elbow,
            pose.right_elbow,
            pose.left_wrist,
            pose.right_wrist,
            pose.left_hip,
            pose.right_hip,
        )
        left_wrist_hip_distance = math.hypot(
            pose.left_wrist.x - pose.left_hip.x,
            pose.left_wrist.y - pose.left_hip.y,
        )
        right_wrist_hip_distance = math.hypot(
            pose.right_wrist.x - pose.right_hip.x,
            pose.right_wrist.y - pose.right_hip.y,
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
        left_elbow_offset = self._outward_offset(
            pose.left_elbow,
            pose.left_shoulder,
            pose,
        )
        right_elbow_offset = self._outward_offset(
            pose.right_elbow,
            pose.right_shoulder,
            pose,
        )

        rules = {
            "upper_body_and_hips_visible": all(
                self._is_visible(point, thresholds.min_visibility)
                for point in relevant_points
            ),
            "left_hand_near_hip": (
                left_wrist_hip_distance <= thresholds.wrist_hip_distance_tolerance
            ),
            "right_hand_near_hip": (
                right_wrist_hip_distance <= thresholds.wrist_hip_distance_tolerance
            ),
            "left_elbow_bent": (
                thresholds.min_elbow_angle
                <= left_elbow_angle
                <= thresholds.max_elbow_angle
            ),
            "right_elbow_bent": (
                thresholds.min_elbow_angle
                <= right_elbow_angle
                <= thresholds.max_elbow_angle
            ),
            "left_elbow_outward": (
                left_elbow_offset >= thresholds.elbow_outward_margin
            ),
            "right_elbow_outward": (
                right_elbow_offset >= thresholds.elbow_outward_margin
            ),
        }
        return self._build_result(
            posture_id=PostureId.HANDS_ON_HIPS,
            rules=rules,
            measurements={
                "minimum_visibility": min(
                    point.visibility for point in relevant_points
                ),
                "left_wrist_hip_distance": left_wrist_hip_distance,
                "right_wrist_hip_distance": right_wrist_hip_distance,
                "left_elbow_angle": left_elbow_angle,
                "right_elbow_angle": right_elbow_angle,
                "left_elbow_outward_offset": left_elbow_offset,
                "right_elbow_outward_offset": right_elbow_offset,
            },
            success_message="Postura de manos en las caderas correcta",
            failure_message="Acerca las manos a las caderas y abre los codos",
        )

    def _evaluate_arms_forward(self, pose: PoseLandmarks) -> PostureResult:
        thresholds = self.arms_forward_thresholds
        points = (
            pose.left_shoulder, pose.right_shoulder, pose.left_elbow,
            pose.right_elbow, pose.left_wrist, pose.right_wrist,
        )
        rules = {
            "upper_body_visible": all(
                self._is_visible(point, thresholds.min_visibility) for point in points
            ),
        }
        measurements = {"minimum_visibility": min(point.visibility for point in points)}
        for side in ("left", "right"):
            shoulder = getattr(pose, f"{side}_shoulder")
            elbow = getattr(pose, f"{side}_elbow")
            wrist = getattr(pose, f"{side}_wrist")
            # En landmarks normalizados de MediaPipe, z menor apunta a la cámara.
            wrist_depth = shoulder.z - wrist.z
            elbow_depth = shoulder.z - elbow.z
            wrist_elbow_depth = elbow.z - wrist.z
            height_delta = abs(wrist.y - shoulder.y)
            lateral_delta = abs(wrist.x - shoulder.x)
            angle = calculate_3d_angle(shoulder, elbow, wrist)
            rules.update({
                f"{side}_wrist_forward": wrist_depth >= thresholds.min_wrist_depth,
                f"{side}_elbow_forward": elbow_depth >= thresholds.min_elbow_depth,
                f"{side}_wrist_beyond_elbow": (
                    wrist_elbow_depth >= thresholds.min_wrist_elbow_depth
                ),
                f"{side}_wrist_at_shoulder_height": (
                    height_delta <= thresholds.wrist_height_tolerance
                ),
                f"{side}_arm_not_open_laterally": (
                    lateral_delta <= thresholds.wrist_lateral_tolerance
                ),
                f"{side}_elbow_extended": (
                    angle >= 180 - thresholds.elbow_straight_tolerance_degrees
                ),
            })
            measurements.update({
                f"{side}_wrist_depth": wrist_depth,
                f"{side}_elbow_depth": elbow_depth,
                f"{side}_wrist_elbow_depth": wrist_elbow_depth,
                f"{side}_wrist_height_delta": height_delta,
                f"{side}_wrist_lateral_delta": lateral_delta,
                f"{side}_elbow_angle": angle,
            })
        return self._build_result(
            posture_id=PostureId.ARMS_FORWARD,
            rules=rules,
            measurements=measurements,
            success_message="Brazos al frente correctos",
            failure_message="Extiende ambos brazos al frente a la altura de hombros",
        )

    def _evaluate_squat(self, pose: PoseLandmarks) -> PostureResult:
        thresholds = self.squat_thresholds
        points = (
            pose.left_shoulder, pose.right_shoulder, pose.left_hip,
            pose.right_hip, pose.left_knee, pose.right_knee,
            pose.left_ankle, pose.right_ankle,
        )
        rules = {
            "body_visible": all(
                self._is_visible(point, thresholds.min_visibility) for point in points
            ),
        }
        measurements = {"minimum_visibility": min(point.visibility for point in points)}
        for side in ("left", "right"):
            shoulder = getattr(pose, f"{side}_shoulder")
            hip = getattr(pose, f"{side}_hip")
            knee = getattr(pose, f"{side}_knee")
            ankle = getattr(pose, f"{side}_ankle")
            knee_angle = calculate_3d_angle(hip, knee, ankle)
            shoulder_hip_gap = hip.y - shoulder.y
            hip_knee_gap = knee.y - hip.y
            knee_ankle_gap = ankle.y - knee.y
            rules.update({
                f"{side}_knee_bent": (
                    thresholds.min_knee_angle <= knee_angle <= thresholds.max_knee_angle
                ),
                f"{side}_shoulder_above_hip": (
                    shoulder_hip_gap >= thresholds.min_shoulder_hip_gap
                ),
                f"{side}_hip_above_knee": (
                    hip_knee_gap >= thresholds.min_hip_knee_gap
                ),
                f"{side}_knee_above_ankle": (
                    knee_ankle_gap >= thresholds.min_knee_ankle_gap
                ),
            })
            measurements.update({
                f"{side}_knee_angle": knee_angle,
                f"{side}_shoulder_hip_gap": shoulder_hip_gap,
                f"{side}_hip_knee_gap": hip_knee_gap,
                f"{side}_knee_ankle_gap": knee_ankle_gap,
            })
        return self._build_result(
            posture_id=PostureId.SQUAT,
            rules=rules,
            measurements=measurements,
            success_message="Sentadilla estática detectada",
            failure_message="Flexiona ambas rodillas suavemente y muestra el cuerpo completo",
        )

    @staticmethod
    def _build_result(
        posture_id: PostureId,
        rules: dict[str, bool],
        measurements: dict[str, float],
        success_message: str,
        failure_message: str,
    ) -> PostureResult:
        failed_rules = tuple(name for name, passed in rules.items() if not passed)
        detected = not failed_rules
        return PostureResult(
            posture_id=posture_id,
            detected=detected,
            confidence=sum(rules.values()) / len(rules),
            message=success_message if detected else failure_message,
            measurements=measurements,
            failed_rules=failed_rules,
        )

    @staticmethod
    def _outward_offset(
        point: PoseLandmark,
        shoulder: PoseLandmark,
        pose: PoseLandmarks,
    ) -> float:
        shoulder_center_x = (pose.left_shoulder.x + pose.right_shoulder.x) / 2
        direction = 1.0 if shoulder.x >= shoulder_center_x else -1.0
        return (point.x - shoulder.x) * direction

    def _is_visible(
        self,
        landmark: PoseLandmark,
        min_visibility: float | None = None,
    ) -> bool:
        threshold = (
            self.thresholds.min_visibility
            if min_visibility is None
            else min_visibility
        )
        return landmark.visibility >= threshold
