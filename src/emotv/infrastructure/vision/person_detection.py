"""Detección de personas en las imágenes que suben los usuarios.

Busca rostros (YuNet) y cuerpos (MediaPipe Pose) con los modelos que ya usa
EMOtv. Todo ocurre en memoria: la imagen se reduce a 1280 px por lado, se
analiza y se descarta. Solo devuelve la confianza de que haya una persona; no
reconoce a nadie, no compara rostros y no guarda plantillas ni recortes.

La detección no es infalible: por eso la revisión del docente sigue siendo
obligatoria.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np

from emotv.infrastructure.vision.stimulus_image import InvalidStimulusImage

DETECTION_SIDE = 1280
# Confianza (0 a 1) de que el cuadro muestre un rostro o un cuerpo.
FrameScore = Callable[[np.ndarray], float]


class PersonCheckUnavailable(RuntimeError):
    """Faltan los modelos de detección: no se aceptan imágenes sin revisarlas."""


@dataclass(frozen=True, slots=True)
class PersonCheck:
    face: float
    body: float

    @property
    def confidence(self) -> float:
        return max(self.face, self.body)


def prepare(data: bytes, max_side: int = DETECTION_SIDE) -> np.ndarray:
    """Decodifica en memoria (BGR, sin transparencia) y reduce el lado mayor."""
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise InvalidStimulusImage("No se pudo leer la imagen")
    height, width = image.shape[:2]
    scale = max_side / max(height, width)
    if scale < 1:
        image = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))),
                           interpolation=cv2.INTER_AREA)
    return image


class ImagePersonDetector:
    """Combina un detector de rostros y uno de cuerpos. Se inyectan como
    funciones para que las pruebas usen detectores falsos, sin pesos."""

    def __init__(self, face: FrameScore, body: FrameScore, max_side: int = DETECTION_SIDE) -> None:
        self.face = face
        self.body = body
        self.max_side = max_side

    def __call__(self, data: bytes) -> PersonCheck:
        frame = prepare(data, self.max_side)
        return PersonCheck(face=float(self.face(frame)), body=float(self.body(frame)))


def create_person_detector(min_confidence: float) -> ImagePersonDetector:
    """Detector con los modelos instalados. min_confidence es el umbral de
    revisión: se piden también las detecciones dudosas para poder marcarlas.
    Los modelos se cargan al primer uso; si faltan, PersonCheckUnavailable."""
    lock = threading.Lock()
    faces: list = []

    def face(frame: np.ndarray) -> float:
        from emotv.infrastructure.vision.face_detection.yunet_face_detector import YuNetFaceDetector

        with lock:
            try:
                if not faces:
                    faces.append(YuNetFaceDetector(confidence_threshold=min_confidence))
                found = faces[0].detect(frame)
            except (FileNotFoundError, ValueError) as error:
                raise PersonCheckUnavailable("No está disponible el detector de rostros") from error
        return max((item.confidence for item in found), default=0.0)

    def body(frame: np.ndarray) -> float:
        from emotv.infrastructure.vision.pose_detection.pose_detector import PoseDetector

        # Un detector nuevo por imagen: en modo video arrastraría la pose de la anterior.
        try:
            with PoseDetector(min_detection_confidence=min_confidence) as detector:
                result = detector.detect(frame)
        except FileNotFoundError as error:
            raise PersonCheckUnavailable("No está disponible el detector de cuerpos") from error
        if not result.detected:
            return 0.0
        # Hubo detección por encima del umbral de revisión; la visibilidad media la gradúa.
        return max(min_confidence, float(result.confidence or 0.0))

    return ImagePersonDetector(face, body)
