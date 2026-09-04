from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from emotv.config import (
    POSE_MIN_DETECTION_CONFIDENCE,
    POSE_MIN_PRESENCE_CONFIDENCE,
    POSE_MIN_TRACKING_CONFIDENCE,
    POSE_MODEL_PATH,
)
from emotv.domain.pose_landmarks import PoseLandmark, PoseLandmarks
from emotv.domain.pose_result import PoseResult


class PoseDetector:
    """Detecta una pose corporal con MediaPipe Pose Landmarker."""

    def __init__(self, model_path: str | Path = POSE_MODEL_PATH) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"No se encontro el modelo de pose en {self.model_path}. "
                "Ejecuta: python scripts/poses/download_pose_model.py"
            )

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=POSE_MIN_DETECTION_CONFIDENCE,
            min_pose_presence_confidence=POSE_MIN_PRESENCE_CONFIDENCE,
            min_tracking_confidence=POSE_MIN_TRACKING_CONFIDENCE,
            output_segmentation_masks=False,
        )
        self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1
        self._lock = threading.Lock()
        self._closed = False

    def detect(self, frame: np.ndarray) -> PoseResult:
        """Procesa un frame BGR de OpenCV y devuelve landmarks normalizados."""

        self._validate_frame(frame)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(rgb_frame),
        )

        with self._lock:
            if self._closed:
                raise RuntimeError("PoseDetector ya fue cerrado")
            result = self._landmarker.detect_for_video(
                image,
                self._next_timestamp_ms(),
            )

        if not result.pose_landmarks:
            return PoseResult(detected=False)

        landmarks = self._to_domain_landmarks(result.pose_landmarks[0])
        return PoseResult(
            detected=True,
            landmarks=landmarks,
            confidence=self._mean_visibility(landmarks),
        )

    def close(self) -> None:
        """Libera los recursos nativos utilizados por MediaPipe."""

        with self._lock:
            if not self._closed:
                self._landmarker.close()
                self._closed = True

    def __enter__(self) -> PoseDetector:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def _next_timestamp_ms(self) -> int:
        timestamp_ms = time.monotonic_ns() // 1_000_000
        timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        return timestamp_ms

    @staticmethod
    def _validate_frame(frame: np.ndarray) -> None:
        if not isinstance(frame, np.ndarray):
            raise TypeError("frame debe ser un numpy.ndarray")
        if frame.dtype != np.uint8:
            raise ValueError("frame debe tener dtype uint8")
        if frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0:
            raise ValueError("frame debe ser una imagen BGR no vacia con 3 canales")

    @classmethod
    def _to_domain_landmarks(cls, source: list[Any]) -> PoseLandmarks:
        landmark_name = mp.tasks.vision.PoseLandmark

        def get(name: Any) -> PoseLandmark:
            landmark = source[name.value]
            return PoseLandmark(
                x=float(landmark.x),
                y=float(landmark.y),
                z=float(landmark.z or 0.0),
                visibility=float(landmark.visibility or 0.0),
            )

        return PoseLandmarks(
            nose=get(landmark_name.NOSE),
            left_shoulder=get(landmark_name.LEFT_SHOULDER),
            right_shoulder=get(landmark_name.RIGHT_SHOULDER),
            left_elbow=get(landmark_name.LEFT_ELBOW),
            right_elbow=get(landmark_name.RIGHT_ELBOW),
            left_wrist=get(landmark_name.LEFT_WRIST),
            right_wrist=get(landmark_name.RIGHT_WRIST),
            left_hip=get(landmark_name.LEFT_HIP),
            right_hip=get(landmark_name.RIGHT_HIP),
            left_knee=get(landmark_name.LEFT_KNEE),
            right_knee=get(landmark_name.RIGHT_KNEE),
            left_ankle=get(landmark_name.LEFT_ANKLE),
            right_ankle=get(landmark_name.RIGHT_ANKLE),
        )

    @staticmethod
    def _mean_visibility(landmarks: PoseLandmarks) -> float:
        values = [
            landmark.visibility
            for landmark in (
                landmarks.nose,
                landmarks.left_shoulder,
                landmarks.right_shoulder,
                landmarks.left_elbow,
                landmarks.right_elbow,
                landmarks.left_wrist,
                landmarks.right_wrist,
                landmarks.left_hip,
                landmarks.right_hip,
                landmarks.left_knee,
                landmarks.right_knee,
                landmarks.left_ankle,
                landmarks.right_ankle,
            )
        ]
        return sum(values) / len(values)
