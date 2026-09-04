from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PoseLandmark:
    """Punto corporal normalizado detectado en una imagen."""

    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


@dataclass(frozen=True, slots=True)
class PoseLandmarks:
    """Landmarks necesarios para validar las primeras posturas de EMOtv."""

    nose: PoseLandmark
    left_shoulder: PoseLandmark
    right_shoulder: PoseLandmark
    left_elbow: PoseLandmark
    right_elbow: PoseLandmark
    left_wrist: PoseLandmark
    right_wrist: PoseLandmark
    left_hip: PoseLandmark
    right_hip: PoseLandmark
    left_knee: PoseLandmark
    right_knee: PoseLandmark
    left_ankle: PoseLandmark
    right_ankle: PoseLandmark
