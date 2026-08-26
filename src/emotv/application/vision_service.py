from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from emotv.config import TARGET_WIDTH, TARGET_HEIGHT, TARGET_FPS
from emotv.infrastructure.vision.camera.opencv_camera import OpenCVCamera, CameraConfig
from emotv.infrastructure.vision.face_detection.yunet_face_detector import YuNetFaceDetector
from emotv.infrastructure.vision.face_processing.face_preprocessor import FacePreprocessor
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import EmotionClassifier
from emotv.shared.performance.monitor import PerformanceMonitor


@dataclass
class VisionResult:
    frame: np.ndarray
    detections: list
    emotion: str
    confidence: float
    fps: float
    cpu: float
    ram: float


class VisionService:
    def __init__(self, camera_index: int = 0, width: int = TARGET_WIDTH, height: int = TARGET_HEIGHT, fps: int = TARGET_FPS):
        config = CameraConfig(device_index=camera_index, width=width, height=height, fps=fps)
        self.camera = OpenCVCamera(config)
        self.detector = YuNetFaceDetector(input_size=(width, height))
        self.preprocessor = FacePreprocessor()
        self.classifier = EmotionClassifier()
        self.monitor = PerformanceMonitor()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._last_frame: Optional[np.ndarray] = None
        self._last_emotion = ("neutral", 0.0)
        self._last_detections = []
        self._frame_counter = 0
        self._skip_interval = 2

    def start(self) -> None:
        if self._running:
            return
        self.camera.open()
        if not self.camera.is_opened:
            raise RuntimeError("No se pudo abrir la cámara.")
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.camera.release()

    def _process_loop(self) -> None:
        while self._running:
            frame = self.camera.read()
            if frame is None:
                time.sleep(0.01)
                continue

            self.monitor.update_frame()
            self._frame_counter += 1

            if self._frame_counter % self._skip_interval == 0:
                detections = self.detector.detect(frame)
                self._last_detections = detections
                if detections:
                    cropped = self.preprocessor.process(frame, detections[0])
                    if cropped and cropped.is_valid:
                        emotion, conf = self.classifier.predict(cropped)
                        self._last_emotion = (emotion, conf)
            else:
                detections = self._last_detections

            annotated = self._annotate_frame(frame, detections)
            with self._lock:
                self._last_frame = annotated
            time.sleep(0.001)

    def _annotate_frame(self, frame: np.ndarray, detections: list) -> np.ndarray:
        display = frame.copy()
        for face in detections:
            x, y, w, h = face.bbox
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
            if face == detections[0]:
                emotion, conf = self._last_emotion
                label = f"{emotion} ({conf*100:.1f}%)"
                cv2.putText(display, label, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        stats = self.monitor.get_stats()
        lines = [
            f"FPS: {stats.fps:.1f}",
            f"CPU: {stats.cpu_percent:.1f}%",
            f"RAM: {stats.ram_mb:.1f} MB",
            f"Faces: {len(detections)}",
            f"Emotion: {self._last_emotion[0]} ({self._last_emotion[1]*100:.1f}%)",
        ]
        for i, line in enumerate(lines):
            cv2.putText(display, line, (15, 30 + i * 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        return display

    def get_current_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._last_frame.copy() if self._last_frame is not None else None

    def get_current_emotion(self) -> tuple[str, float]:
        return self._last_emotion

    def get_current_stats(self) -> dict:
        stats = self.monitor.get_stats()
        return {
            "fps": stats.fps,
            "cpu_percent": stats.cpu_percent,
            "ram_mb": stats.ram_mb,
            "elapsed_seconds": stats.elapsed_seconds,
            "emotion": self._last_emotion[0],
            "confidence": self._last_emotion[1],
            "faces_detected": len(self._last_detections),
        }

    @property
    def is_running(self) -> bool:
        return self._running