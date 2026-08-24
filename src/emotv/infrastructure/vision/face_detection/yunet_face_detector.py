from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class FaceDetection:
    """
    Información correspondiente a un rostro detectado.
    """

    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """
        Devuelve la caja delimitadora como:
        (x, y, width, height)
        """
        return self.x, self.y, self.width, self.height


class YuNetFaceDetector:
    """
    Detector facial basado en YuNet.

    Utiliza cv2.FaceDetectorYN para realizar la inferencia.

    Responsabilidades:
    - Cargar el modelo YuNet.
    - Configurar el tamaño de entrada.
    - Detectar rostros.
    - Convertir los resultados del modelo a objetos FaceDetection.

    No debe encargarse de:
    - Abrir la cámara.
    - Mostrar imágenes.
    - Clasificar emociones.
    """

    def __init__(
        self,
        model_path: str | Path,
        input_size: tuple[int, int] = (640, 480),
        confidence_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ) -> None:
        self.model_path = Path(model_path)
        self.input_size = input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.top_k = top_k

        self._detector: cv2.FaceDetectorYN | None = None

        self._validate_model()
        self._create_detector()

    def _validate_model(self) -> None:
        """
        Comprueba que el archivo del modelo exista.
        """
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"No se encontró el modelo YuNet: "
                f"{self.model_path}"
            )

        if self.model_path.stat().st_size == 0:
            raise ValueError(
                f"El modelo YuNet está vacío: "
                f"{self.model_path}"
            )

    def _create_detector(self) -> None:
        """
        Crea la instancia de FaceDetectorYN.
        """
        self._detector = cv2.FaceDetectorYN.create(
            model=str(self.model_path),
            config="",
            input_size=self.input_size,
            score_threshold=self.confidence_threshold,
            nms_threshold=self.nms_threshold,
            top_k=self.top_k,
        )

    def set_input_size(
        self,
        width: int,
        height: int,
    ) -> None:
        """
        Actualiza el tamaño de entrada utilizado por YuNet.
        """
        if width <= 0 or height <= 0:
            raise ValueError(
                "El ancho y alto deben ser mayores que cero."
            )

        self.input_size = (width, height)

        if self._detector is None:
            raise RuntimeError(
                "El detector YuNet no está inicializado."
            )

        self._detector.setInputSize(
            self.input_size
        )

    def detect(
        self,
        frame: np.ndarray,
    ) -> list[FaceDetection]:
        """
        Detecta rostros en un frame.

        Args:
            frame:
                Imagen BGR obtenida normalmente desde OpenCV.

        Returns:
            list[FaceDetection]:
                Lista de rostros detectados.
        """
        if self._detector is None:
            raise RuntimeError(
                "El detector YuNet no está inicializado."
            )

        if frame is None or frame.size == 0:
            raise ValueError(
                "El frame proporcionado está vacío."
            )

        height, width = frame.shape[:2]

        # YuNet debe conocer el tamaño real del frame.
        self.set_input_size(width, height)

        _, faces = self._detector.detect(frame)

        if faces is None:
            return []

        detections: list[FaceDetection] = []

        for face in faces:
            x = int(face[0])
            y = int(face[1])
            face_width = int(face[2])
            face_height = int(face[3])

            confidence = float(face[14])

            detections.append(
                FaceDetection(
                    x=x,
                    y=y,
                    width=face_width,
                    height=face_height,
                    confidence=confidence,
                )
            )

        return detections

    @property
    def name(self) -> str:
        """
        Nombre del detector.
        """
        return "YuNet"