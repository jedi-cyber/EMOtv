from __future__ import annotations

from typing import Protocol

import numpy as np

from emotv.domain.pose_result import PoseResult
from emotv.domain.posture_id import PostureId
from emotv.domain.posture_result import PostureResult
from emotv.infrastructure.vision.movement_analysis.posture_validator import (
    PostureValidator,
)
from emotv.infrastructure.vision.pose_detection.pose_detector import PoseDetector


class PoseDetectorProtocol(Protocol):
    def detect(self, frame: np.ndarray) -> PoseResult: ...


class PoseService:

    def __init__(
        self,
        detector: PoseDetectorProtocol | None = None,
        validator: PostureValidator | None = None,
    ) -> None:
        self.detector = detector or PoseDetector()
        self.validator = validator or PostureValidator()
        self._last_pose_result: PoseResult | None = None

    @property
    def last_pose_result(self) -> PoseResult | None:
        return self._last_pose_result

    def analyze(self, frame: np.ndarray) -> dict[str, bool] | None:
        result = self.validate(frame, PostureId.ARMS_UP)
        if result is None:
            return None
        return {
            "pose_detected": True,
            "arms_up": result.detected,
        }

    def validate(
        self,
        frame: np.ndarray,
        posture_id: PostureId | str,
    ) -> PostureResult | None:
        """Detecta landmarks y evalúa la postura solicitada."""

        pose = self.detector.detect(frame)
        self._last_pose_result = pose
        if not pose.detected or pose.landmarks is None:
            return None
        return self.validator.validate(pose.landmarks, posture_id)

    def close(self) -> None:
        close = getattr(self.detector, "close", None)
        if callable(close):
            close()
