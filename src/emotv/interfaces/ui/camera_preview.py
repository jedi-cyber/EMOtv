from __future__ import annotations

import cv2
import numpy as np

from emotv.infrastructure.vision.camera.opencv_camera import OpenCVCamera
from emotv.shared.performance.monitor import PerformanceMonitor


class CameraPreview:
    """
    Vista temporal de cámara para EMOtv.

    Responsabilidades:
    - Mostrar los frames obtenidos desde OpenCVCamera.
    - Superponer métricas de FPS, CPU y RAM.
    - Detectar la tecla de salida.
    - Mantener separada la visualización de la lógica de cámara.

    No debe encargarse de:
    - Detectar rostros.
    - Clasificar emociones.
    - Gestionar modelos de IA.
    - Guardar video.
    """

    def __init__(
        self,
        camera: OpenCVCamera,
        monitor: PerformanceMonitor,
        window_name: str = "EMOtv - Camera Preview",
        exit_key: str = "q",
    ) -> None:
        if len(exit_key) != 1:
            raise ValueError(
                "exit_key debe contener exactamente un carácter."
            )

        self.camera = camera
        self.monitor = monitor
        self.window_name = window_name
        self.exit_key = exit_key.lower()

        self._running = False

    def run(self) -> None:
        """
        Inicia el bucle de visualización de la cámara.

        La cámara debe encontrarse abierta antes de llamar a este método.
        """
        if not self.camera.is_opened:
            raise RuntimeError(
                "La cámara debe estar abierta antes de iniciar CameraPreview."
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

                display_frame = self._prepare_frame(frame)

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
        Solicita detener el bucle de visualización.
        """
        self._running = False

    def _prepare_frame(
        self,
        frame: np.ndarray,
    ) -> np.ndarray:
        """
        Prepara una copia del frame para visualización.

        No modifica el frame original recibido desde la cámara.

        Returns:
            np.ndarray:
                Frame con información de rendimiento.
        """
        display_frame = frame.copy()

        self._draw_performance_info(display_frame)
        self._draw_exit_message(display_frame)

        return display_frame

    def _draw_performance_info(
        self,
        frame: np.ndarray,
    ) -> None:
        """
        Dibuja las métricas actuales sobre la imagen.
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
                frame=frame,
                text=text,
                position=(start_x, y),
            )

    def _draw_exit_message(
        self,
        frame: np.ndarray,
    ) -> None:
        """
        Muestra una pequeña indicación para cerrar la vista.
        """
        height, _ = frame.shape[:2]

        text = f"Presiona '{self.exit_key.upper()}' para salir"

        self._draw_text(
            frame=frame,
            text=text,
            position=(15, height - 20),
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
        Dibuja texto legible sobre un frame.
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 2

        # Borde oscuro para mejorar legibilidad
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

        # Texto principal
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

        Returns:
            bool:
                True si se presionó la tecla de salida o
                si la ventana fue cerrada manualmente.
        """
        key = cv2.waitKey(1) & 0xFF

        if key == ord(self.exit_key):
            return True

        try:
            window_visible = cv2.getWindowProperty(
                self.window_name,
                cv2.WND_PROP_VISIBLE,
            )

            if window_visible < 1:
                return True

        except cv2.error:
            return True

        return False