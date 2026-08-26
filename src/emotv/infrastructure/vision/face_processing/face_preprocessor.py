from __future__ import annotations

import cv2
import numpy as np

from emotv.config import (
    FACE_PADDING_RATIO,
    FACE_TARGET_SIZE,
    PREPROCESS_GRAYSCALE,
    PREPROCESS_NORMALIZE,
)
from emotv.domain.cropped_face import CroppedFace
from emotv.infrastructure.vision.face_detection.yunet_face_detector import (
    FaceDetection,
)


class FacePreprocessor:
    """
    Se encarga de recortar, redimensionar y normalizar los rostros detectados.

    Responsabilidades:
    - Extraer el ROI (región de interés) del rostro usando las coordenadas.
    - Aplicar padding para incluir contexto.
    - Redimensionar a un tamaño fijo.
    - Convertir a escala de grises (opcional).
    - Normalizar píxeles (opcional).

    No debe encargarse de:
    - Detectar rostros.
    - Clasificar emociones.
    - Mostrar imágenes.
    """

    def __init__(
        self,
        padding_ratio: float = FACE_PADDING_RATIO,
        target_size: tuple[int, int] = FACE_TARGET_SIZE,
        grayscale: bool = PREPROCESS_GRAYSCALE,
        normalize: bool = PREPROCESS_NORMALIZE,
    ) -> None:
        self.padding_ratio = padding_ratio
        self.target_size = target_size
        self.grayscale = grayscale
        self.normalize = normalize

    def process(
        self,
        frame: np.ndarray,
        detection: FaceDetection,
    ) -> CroppedFace | None:
        """
        Recorta y preprocesa un rostro detectado.

        Args:
            frame: Imagen BGR completa.
            detection: Detección del rostro.

        Returns:
            CroppedFace | None: Rostro preprocesado, o None si el recorte es inválido.
        """
        if frame is None or frame.size == 0:
            return None

        height, width = frame.shape[:2]
        x, y, w, h = detection.bbox

        # 1. Calcular padding (basado en el tamaño del rostro)
        padding = int(max(w, h) * self.padding_ratio)

        # 2. Aplicar padding y asegurar que no salga de los límites
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(width, x + w + padding)
        y2 = min(height, y + h + padding)

        # 3. Recortar la región de interés (ROI)
        roi = frame[y1:y2, x1:x2]

        # 4. Verificar que el recorte sea válido
        if roi is None or roi.size == 0:
            return None

        # 5. Redimensionar al tamaño objetivo
        roi_resized = cv2.resize(roi, self.target_size, interpolation=cv2.INTER_AREA)

        # 6. Convertir a escala de grises si está configurado
        if self.grayscale:
            if len(roi_resized.shape) == 3 and roi_resized.shape[2] == 3:
                roi_resized = cv2.cvtColor(roi_resized, cv2.COLOR_BGR2GRAY)
            # Si ya está en grises (2D), lo dejamos igual

        # 7. Normalizar píxeles a [0, 1] si está configurado
        if self.normalize:
            roi_resized = roi_resized.astype(np.float32) / 255.0
        else:
            roi_resized = roi_resized.astype(np.uint8)

        # 8. Crear el objeto CroppedFace con la nueva bbox (con padding)
        cropped_face = CroppedFace(
            image=roi_resized,
            bbox=(x1, y1, x2, y2),
            confidence=detection.confidence,
        )

        return cropped_face