from __future__ import annotations

import cv2
import numpy as np

from emotv.infrastructure.vision.camera.opencv_camera import OpenCVCamera
from emotv.infrastructure.vision.face_detection.yunet_face_detector import (
    YuNetFaceDetector,
)
from emotv.shared.performance.monitor import PerformanceMonitor


class FaceDetectionPreview:
    """
    Vista temporal para probar la detección facial con YuNet.

    Responsabilidades:
    - Obtener frames desde OpenCVCamera.
    - Ejecutar YuNet sobre los frames.
    - Dibujar los rostros detectados.
    - Mostrar FPS, CPU y RAM.
    """

    def __init__(
        self,
        camera: OpenCVCamera,
        detector: YuNetFaceDetector,
        monitor: PerformanceMonitor,
        window_name: str = "EMOtv - Face Detection",
        exit_key: str = "q",
    ) -> None:
        if len(exit_key) != 1:
            raise ValueError(
                "exit_key debe contener exactamente un carácter."
            )

        self.camera = camera
        self.detector = detector
        self.monitor = monitor
        self.window_name = window_name
        self.exit_key = exit_key.lower()

        self._running = False

    def run(self) -> None:
        """
        Inicia el preview de detección facial.
        """
        if not self.camera.is_opened:
            raise RuntimeError(
                "La cámara debe estar abierta antes de iniciar "
                "FaceDetectionPreview."
            )

        self._running = True

        cv2.namedWindow(
            self.window_name,
            cv2.WINDOW_NORMAL,
        )

        try:
            while self._running:
                frame = self.camera.read()

                self.monitor.update_frame()

                detections = self.detector.detect(frame)

                display_frame = self._prepare_frame(
                    frame,
                    detections,
                )

                cv2.imshow(
                    self.window_name,
                    display_frame,
                )

                if self._should_close():
                    self.stop()

        finally:
            cv2.destroyWindow(self.window_name)

    def stop(self) -> None:
        """
        Detiene el preview.
        """
        self._running = False

    def _prepare_frame(
        self,
        frame: np.ndarray,
        detections,
    ) -> np.ndarray:
        """
        Prepara el frame para visualización.
        """
        display_frame = frame.copy()

        self._draw_faces(
            display_frame,
            detections,
        )

        self._draw_performance_info(
            display_frame,
        )

        self._draw_exit_message(
            display_frame,
        )

        return display_frame

    def _draw_faces(
        self,
        frame: np.ndarray,
        detections,
    ) -> None:
        """
        Dibuja las cajas de los rostros detectados.
        """
        for face in detections:
            x, y, width, height = face.bbox

            cv2.rectangle(
                frame,
                (x, y),
                (x + width, y + height),
                (0, 255, 0),
                2,
            )

            confidence_text = (
                f"Rostro: {face.confidence * 100:.1f}%"
            )

            text_position = (
                x,
                max(y - 10, 20),
            )

            self._draw_text(
                frame,
                confidence_text,
                text_position,
            )

    def _draw_performance_info(
        self,
        frame: np.ndarray,
    ) -> None:
        """
        Dibuja FPS, CPU y RAM.
        """
        stats = self.monitor.get_stats()

        lines = [
            f"FPS: {stats.fps:.1f}",
            f"CPU: {stats.cpu_percent:.1f}%",
            f"RAM: {stats.ram_mb:.1f} MB",
        ]

        start_x = 15
        start_y = 30
        line_height = 28

        for index, text in enumerate(lines):
            y = start_y + (index * line_height)

            self._draw_text(
                frame,
                text,
                (start_x, y),
            )

    def _draw_exit_message(
        self,
        frame: np.ndarray,
    ) -> None:
        """
        Muestra la tecla utilizada para cerrar.
        """
        height = frame.shape[0]

        text = f"Presiona '{self.exit_key.upper()}' para salir"

        self._draw_text(
            frame,
            text,
            (15, height - 20),
            font_scale=0.55,
        )

    @staticmethod
    def _draw_text(
        frame: np.ndarray,
        text: str,
        position: tuple[int, int],
        font_scale: float = 0.65,
    ) -> None:
        """
        Dibuja texto con borde para mejorar la visibilidad.
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 2

        # Borde
        cv2.putText(
            frame,
            text,
            position,
            font,
            font_scale,
            (0, 0, 0),
            thickness + 2,
            cv2.LINE_AA,
        )

        # Texto
        cv2.putText(
            frame,
            text,
            position,
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    def _should_close(self) -> bool:
        """
        Comprueba si el usuario quiere cerrar la ventana.
        """
        key = cv2.waitKey(1) & 0xFF

        if key == ord(self.exit_key):
            return True

        try:
            visible = cv2.getWindowProperty(
                self.window_name,
                cv2.WND_PROP_VISIBLE,
            )

            if visible < 1:
                return True

        except cv2.error:
            return True

        return False