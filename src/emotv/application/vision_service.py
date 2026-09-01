from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from emotv.config import MAX_VIDEO_FPS, TARGET_WIDTH, TARGET_HEIGHT, TARGET_FPS
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
        effective_fps = min(max(fps, 1), MAX_VIDEO_FPS)
        config = CameraConfig(
            device_index=camera_index,
            width=width,
            height=height,
            fps=effective_fps,
        )
        self.camera = OpenCVCamera(config)
        self.detector = YuNetFaceDetector(input_size=(width, height))
        self.preprocessor = FacePreprocessor()
        self.classifier = EmotionClassifier()
        self.monitor = PerformanceMonitor()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._stream_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._frame_ready = threading.Condition()

        self._last_frame: Optional[np.ndarray] = None
        self._last_jpeg: Optional[bytes] = None
        self._captured_frame: Optional[np.ndarray] = None
        self._captured_frame_id = 0
        self._last_emotion = ("neutral", 0.0)
        self._last_detections = []
        self._frame_counter = 0
        self._skip_interval = 2
        self._stream_fps = effective_fps

    def start(self) -> None:
        if self._running:
            return
        self.camera.open()
        if not self.camera.is_opened:
            raise RuntimeError("No se pudo abrir la cámara.")
        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="camera-capture",
        )
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._stream_thread = threading.Thread(
            target=self._stream_loop, daemon=True, name="video-stream"
        )
        self._capture_thread.start()
        self._thread.start()
        self._stream_thread.start()

    def stop(self) -> None:
        self._running = False
        with self._frame_ready:
            self._frame_ready.notify_all()
        # Libera primero el dispositivo para desbloquear una lectura pendiente.
        self.camera.release()
        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._stream_thread:
            self._stream_thread.join(timeout=2.0)

    def _capture_loop(self) -> None:
        """Lee la cámara continuamente y descarta frames atrasados."""
        while self._running:
            try:
                frame = self.camera.read()
            except RuntimeError:
                if self._running:
                    time.sleep(0.01)
                continue

            # Solo se conserva el último frame. Así, la inferencia nunca procesa
            # una cola de video antigua cuando tarda más que la cámara.
            with self._frame_ready:
                self._captured_frame = frame
                self._captured_frame_id += 1
                self._frame_ready.notify()

    def _process_loop(self) -> None:
        processed_frame_id = 0
        while self._running:
            with self._frame_ready:
                self._frame_ready.wait_for(
                    lambda: (
                        not self._running
                        or self._captured_frame_id != processed_frame_id
                    ),
                    timeout=0.5,
                )
                if not self._running:
                    break
                if self._captured_frame is None:
                    continue
                frame = self._captured_frame
                processed_frame_id = self._captured_frame_id

            self._frame_counter += 1

            if self._frame_counter % self._skip_interval == 0:
                detections = self.detector.detect(frame)
                emotion = None
                if detections:
                    cropped = self.preprocessor.process(frame, detections[0])
                    if cropped and cropped.is_valid:
                        emotion = self.classifier.predict(cropped)

                with self._state_lock:
                    self._last_detections = detections
                    if emotion is not None:
                        self._last_emotion = emotion

    def _stream_loop(self) -> None:
        """Genera el preview con el último frame, sin esperar la inferencia."""
        streamed_frame_id = 0
        interval = 1.0 / self._stream_fps

        while self._running:
            started_at = time.perf_counter()
            with self._frame_ready:
                self._frame_ready.wait_for(
                    lambda: not self._running
                    or self._captured_frame_id != streamed_frame_id,
                    timeout=interval,
                )
                if not self._running:
                    break
                if self._captured_frame is None:
                    continue
                frame = self._captured_frame
                streamed_frame_id = self._captured_frame_id

            with self._state_lock:
                detections = list(self._last_detections)
                emotion = self._last_emotion

            self.monitor.update_frame()
            annotated = self._annotate_frame(frame, detections, emotion)
            success, jpeg = cv2.imencode(
                ".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )
            if success:
                with self._lock:
                    self._last_frame = annotated
                    self._last_jpeg = jpeg.tobytes()

            remaining = interval - (time.perf_counter() - started_at)
            if remaining > 0:
                time.sleep(remaining)

    def _annotate_frame(
        self,
        frame: np.ndarray,
        detections: list,
        emotion: tuple[str, float],
    ) -> np.ndarray:
        display = frame.copy()
        for face in detections:
            x, y, w, h = face.bbox
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
            if face == detections[0]:
                label_emotion, conf = emotion
                label = f"{label_emotion} ({conf*100:.1f}%)"
                cv2.putText(display, label, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        stats = self.monitor.get_stats()
        lines = [
            f"FPS: {stats.fps:.1f}",
            f"CPU: {stats.cpu_percent:.1f}%",
            f"RAM: {stats.ram_mb:.1f} MB",
            f"Faces: {len(detections)}",
            f"Emotion: {emotion[0]} ({emotion[1]*100:.1f}%)",
        ]
        for i, line in enumerate(lines):
            cv2.putText(display, line, (15, 30 + i * 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        return display

    def get_current_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._last_frame.copy() if self._last_frame is not None else None

    def get_current_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._last_jpeg

    def get_current_emotion(self) -> tuple[str, float]:
        with self._state_lock:
            return self._last_emotion

    def get_current_stats(self) -> dict:
        stats = self.monitor.get_stats()
        with self._state_lock:
            emotion = self._last_emotion
            faces_detected = len(self._last_detections)
        return {
            "fps": stats.fps,
            "cpu_percent": stats.cpu_percent,
            "ram_mb": stats.ram_mb,
            "elapsed_seconds": stats.elapsed_seconds,
            "emotion": emotion[0],
            "confidence": emotion[1],
            "faces_detected": faces_detected,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stream_fps(self) -> int:
        """FPS efectivo del preview, limitado a MAX_VIDEO_FPS."""
        return self._stream_fps
