from __future__ import annotations

import numpy as np
from typing import Protocol

from emotv.domain.pose_result import PoseResult
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

    def analyze(self, frame: np.ndarray) -> dict[str, bool] | None:

        pose = self.detector.detect(frame)

        if not pose.detected:
            return None

        assert pose.landmarks is not None
        arms_up = self.validator.both_arms_up(pose.landmarks)

        return {
            "pose_detected": True,
            "arms_up": arms_up
        }
