from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class CameraConfig:
    """
    Configuración básica para una cámara compatible con OpenCV.
    """

    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 15
    backend: int | None = None


class OpenCVCamera:
    """
    Adaptador de cámara basado en OpenCV.

    Responsabilidades:
    - Abrir una cámara.
    - Configurar resolución y FPS.
    - Leer frames.
    - Consultar el estado del dispositivo.
    - Liberar correctamente los recursos.

    Esta clase no debe encargarse de:
    - Mostrar ventanas.
    - Detectar rostros.
    - Ejecutar modelos de IA.
    - Medir CPU o RAM.
    """

    def __init__(self, config: CameraConfig | None = None) -> None:
        self.config = config or CameraConfig()
        self._capture: cv2.VideoCapture | None = None

    @property
    def is_opened(self) -> bool:
        """
        Indica si la cámara se encuentra abierta y disponible.
        """
        return self._capture is not None and self._capture.isOpened()

    def open(self) -> None:
        """
        Abre la cámara utilizando la configuración definida.

        Raises:
            RuntimeError:
                Si la cámara no puede abrirse.
        """
        if self.is_opened:
            return

        if self.config.backend is None:
            capture = cv2.VideoCapture(self.config.device_index)
        else:
            capture = cv2.VideoCapture(
                self.config.device_index,
                self.config.backend,
            )

        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                f"No se pudo abrir la cámara con índice "
                f"{self.config.device_index}."
            )

        self._capture = capture
        self._apply_configuration()

    def _apply_configuration(self) -> None:
        """
        Aplica los parámetros solicitados a la cámara.

        OpenCV no garantiza que el dispositivo acepte exactamente
        estos valores. Por ello, posteriormente puede consultarse
        get_actual_properties().
        """
        if not self.is_opened:
            raise RuntimeError(
                "No se puede configurar una cámara que no está abierta."
            )

        assert self._capture is not None

        self._capture.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            self.config.width,
        )

        self._capture.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            self.config.height,
        )

        self._capture.set(
            cv2.CAP_PROP_FPS,
            self.config.fps,
        )

    def read(self) -> np.ndarray:
        """
        Captura y devuelve el frame más reciente disponible.

        Returns:
            np.ndarray:
                Imagen capturada en formato BGR.

        Raises:
            RuntimeError:
                Si la cámara no está abierta o no puede obtenerse
                correctamente un frame.
        """
        if not self.is_opened:
            raise RuntimeError(
                "La cámara no está abierta. Ejecuta open() primero."
            )

        assert self._capture is not None

        success, frame = self._capture.read()

        if not success or frame is None:
            raise RuntimeError(
                "No se pudo obtener un frame válido desde la cámara."
            )

        if frame.size == 0:
            raise RuntimeError(
                "La cámara devolvió un frame vacío."
            )

        return frame

    def get_actual_properties(self) -> dict[str, float]:
        """
        Obtiene los valores reales aplicados por el dispositivo.

        La resolución o FPS reales pueden diferir de los solicitados
        en CameraConfig.

        Returns:
            dict[str, float]:
                Resolución y FPS reportados por OpenCV.
        """
        if not self.is_opened:
            raise RuntimeError(
                "La cámara debe estar abierta para consultar "
                "sus propiedades."
            )

        assert self._capture is not None

        return {
            "width": self._capture.get(
                cv2.CAP_PROP_FRAME_WIDTH
            ),
            "height": self._capture.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            ),
            "fps": self._capture.get(
                cv2.CAP_PROP_FPS
            ),
        }

    def release(self) -> None:
        """
        Libera la cámara y sus recursos asociados.
        """
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> OpenCVCamera:
        """
        Permite utilizar la clase mediante un context manager.

        Ejemplo:

            with OpenCVCamera() as camera:
                frame = camera.read()
        """
        self.open()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.release()