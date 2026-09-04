from __future__ import annotations

from dataclasses import dataclass

from emotv.domain.pose_landmarks import PoseLandmarks


@dataclass(frozen=True, slots=True)
class PoseResult:
    detected: bool
    landmarks: PoseLandmarks | None = None
    confidence: float = 0.0
