from __future__ import annotations

from dataclasses import dataclass, fields

import cv2
import numpy as np

from emotv.config import POSE_MIN_LANDMARK_VISIBILITY
from emotv.domain.pose_landmarks import PoseLandmark, PoseLandmarks


@dataclass(frozen=True, slots=True)
class PoseDrawingStyle:
    landmark_color: tuple[int, int, int] = (0, 255, 255)
    connection_color: tuple[int, int, int] = (0, 200, 0)
    landmark_radius: int = 4
    connection_thickness: int = 2


class PoseDrawer:
    """Dibuja una pose del dominio sin ejecutar deteccion."""

    CONNECTIONS = (
        ("nose", "left_shoulder"),
        ("nose", "right_shoulder"),
        ("left_shoulder", "right_shoulder"),
        ("left_shoulder", "left_elbow"),
        ("left_elbow", "left_wrist"),
        ("right_shoulder", "right_elbow"),
        ("right_elbow", "right_wrist"),
        ("left_shoulder", "left_hip"),
        ("right_shoulder", "right_hip"),
        ("left_hip", "right_hip"),
        ("left_hip", "left_knee"),
        ("left_knee", "left_ankle"),
        ("right_hip", "right_knee"),
        ("right_knee", "right_ankle"),
    )

    def __init__(
        self,
        style: PoseDrawingStyle | None = None,
        min_visibility: float = POSE_MIN_LANDMARK_VISIBILITY,
    ) -> None:
        if not 0.0 <= min_visibility <= 1.0:
            raise ValueError("min_visibility debe estar entre 0 y 1")
        self.style = style or PoseDrawingStyle()
        self.min_visibility = min_visibility

    def draw(self, frame: np.ndarray, pose: PoseLandmarks) -> np.ndarray:
        """Devuelve una copia del frame con landmarks y conexiones."""

        if frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0:
            raise ValueError("frame debe ser una imagen BGR no vacia con 3 canales")

        display = frame.copy()
        height, width = display.shape[:2]

        for start_name, end_name in self.CONNECTIONS:
            start = getattr(pose, start_name)
            end = getattr(pose, end_name)
            if not self._is_visible(start) or not self._is_visible(end):
                continue
            cv2.line(
                display,
                self._to_pixel(start, width, height),
                self._to_pixel(end, width, height),
                self.style.connection_color,
                self.style.connection_thickness,
                cv2.LINE_AA,
            )

        for field in fields(pose):
            landmark = getattr(pose, field.name)
            if not self._is_visible(landmark):
                continue
            cv2.circle(
                display,
                self._to_pixel(landmark, width, height),
                self.style.landmark_radius,
                self.style.landmark_color,
                -1,
                cv2.LINE_AA,
            )

        return display

    def _is_visible(self, landmark: PoseLandmark) -> bool:
        return landmark.visibility >= self.min_visibility

    @staticmethod
    def _to_pixel(
        landmark: PoseLandmark,
        width: int,
        height: int,
    ) -> tuple[int, int]:
        x = min(max(round(landmark.x * (width - 1)), 0), width - 1)
        y = min(max(round(landmark.y * (height - 1)), 0), height - 1)
        return x, y
