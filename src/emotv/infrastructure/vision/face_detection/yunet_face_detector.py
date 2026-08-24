from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Importamos la configuración centralizada
from emotv.config import (
    YUNET_PATH,
    YUNET_CONFIDENCE_THRESHOLD,
    YUNET_NMS_THRESHOLD,
    # FORCE_CPU_BACKEND  # Ya no se usa porque no es soportado por FaceDetectorYN
)


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
        model_path: str | Path | None = None,
        input_size: tuple[int, int] = (640, 480),
        confidence_threshold: float | None = None,
        nms_threshold: float | None = None,
        top_k: int = 5000,
    ) -> None:
        """
        Inicializa el detector YuNet.

        Args:
            model_path:
                Ruta al archivo .onnx. Si es None, usa la ruta definida en config.
            input_size:
                Tamaño (ancho, alto) de la imagen de entrada para el modelo.
            confidence_threshold:
                Umbral de confianza. Si es None, usa el de config.
            nms_threshold:
                Umbral de Non-Maximum Suppression. Si es None, usa el de config.
            top_k:
                Número máximo de detecciones a mantener.
        """
        # --- 1. Resolver la ruta del modelo usando la config si es necesario ---
        if model_path is None:
            model_path = YUNET_PATH
        self.model_path = Path(model_path)

        # --- 2. Resolver umbrales usando la config si no se pasan ---
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else YUNET_CONFIDENCE_THRESHOLD
        )
        self.nms_threshold = (
            nms_threshold
            if nms_threshold is not None
            else YUNET_NMS_THRESHOLD
        )

        self.input_size = input_size
        self.top_k = top_k
        self._detector: cv2.FaceDetectorYN | None = None

        # --- 3. Validar y cargar ---
        self._validate_model()
        self._create_detector()

    def _validate_model(self) -> None:
        """
        Comprueba que el archivo del modelo exista y no esté vacío.
        """
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"No se encontró el modelo YuNet en: {self.model_path}\n"
                "Ejecuta 'python scripts/download_weights.py' para descargarlo."
            )

        if self.model_path.stat().st_size == 0:
            raise ValueError(
                f"El modelo YuNet está vacío: {self.model_path}\n"
                "Elimínalo y vuelve a descargarlo con 'scripts/download_weights.py'."
            )

    def _create_detector(self) -> None:
        """
        Crea la instancia de FaceDetectorYN.

        Nota: cv2.FaceDetectorYN no expone los métodos setPreferableBackend
        ni setPreferableTarget, por lo que el backend es decidido internamente
        por OpenCV. En sistemas sin GPU compatible (como la GT 610), se usará
        CPU por defecto.
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
            raise ValueError("El ancho y alto deben ser mayores que cero.")

        self.input_size = (width, height)

        if self._detector is None:
            raise RuntimeError("El detector YuNet no está inicializado.")

        self._detector.setInputSize(self.input_size)

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
                Lista de rostros detectados. Vacía si no hay ninguno.
        """
        if self._detector is None:
            raise RuntimeError("El detector YuNet no está inicializado.")

        if frame is None or frame.size == 0:
            raise ValueError("El frame proporcionado está vacío.")

        height, width = frame.shape[:2]

        # YuNet debe conocer el tamaño real del frame para escalar correctamente.
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

            # La confianza está en el índice 14 según la doc de YuNet
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