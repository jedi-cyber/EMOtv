"""Control de calidad de una captura y análisis del cuadro en memoria.

Antes de registrar la expresión estimada se comprueba que haya un rostro
centrado, de tamaño suficiente, bien iluminado y sin la cabeza muy inclinada.
El cuadro se descarta al terminar: no se guarda ni sale del servidor.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from emotv.domain.guided_session import FrameAssessment, QualityIssue


@dataclass(frozen=True, slots=True)
class QualityLimits:
    center_margin: float = 0.20     # el centro del rostro cae en el 60 % central del cuadro
    min_face_ratio: float = 0.15    # ancho del rostro respecto al ancho del cuadro
    min_brightness: float = 60.0    # gris medio del rostro (0-255)
    max_brightness: float = 225.0
    max_tilt_degrees: float = 20.0  # inclinación lateral de la cabeza (línea de los ojos)


def quality_issues(frame: np.ndarray, detection, limits: QualityLimits = QualityLimits()) -> tuple[QualityIssue, ...]:
    """Problemas de calidad de un rostro detectado en el cuadro (vacío si está bien)."""
    if detection is None:
        return (QualityIssue.NO_FACE,)
    height, width = frame.shape[:2]
    x, y, w, h = detection.bbox
    issues: list[QualityIssue] = []
    center_x, center_y = (x + w / 2) / width, (y + h / 2) / height
    if not (limits.center_margin <= center_x <= 1 - limits.center_margin
            and limits.center_margin <= center_y <= 1 - limits.center_margin):
        issues.append(QualityIssue.OFF_CENTER)
    if w / width < limits.min_face_ratio:
        issues.append(QualityIssue.TOO_SMALL)
    x0, y0 = max(0, x), max(0, y)
    region = frame[y0:min(height, y + h), x0:min(width, x + w)]
    if region.size:
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if region.ndim == 3 else region
        brightness = float(gray.mean())
        if brightness < limits.min_brightness:
            issues.append(QualityIssue.TOO_DARK)
        elif brightness > limits.max_brightness:
            issues.append(QualityIssue.TOO_BRIGHT)
    right, left = getattr(detection, "right_eye", None), getattr(detection, "left_eye", None)
    if right is not None and left is not None:
        tilt = abs(math.degrees(math.atan2(left[1] - right[1], left[0] - right[0])))
        tilt = min(tilt, 180 - tilt)
        if tilt > limits.max_tilt_degrees:
            issues.append(QualityIssue.TILTED)
    return tuple(issues)


class GuidedFrameAnalyzer:
    """Detecta el rostro, revisa la calidad y estima la expresión con el modelo local."""

    def __init__(self, analyzer, limits: QualityLimits = QualityLimits()) -> None:
        # analyzer: EmotionFrameAnalyzer (detector, preprocesador y clasificador).
        self.analyzer = analyzer
        self.limits = limits

    def assess(self, frame: np.ndarray) -> FrameAssessment:
        detections = self.analyzer.detector.detect(frame)
        detection = detections[0] if detections else None
        issues = quality_issues(frame, detection, self.limits)
        if detection is None:
            return FrameAssessment(issues)
        detailed = self.analyzer.analyze_detailed(frame)
        if detailed is None:
            return FrameAssessment(tuple(dict.fromkeys((*issues, QualityIssue.NO_FACE))))
        (emotion, confidence), distribution = detailed
        return FrameAssessment(issues, emotion, float(confidence),
                               {key: float(value) for key, value in distribution.items()} if distribution else None)


def decode_frame(data: bytes) -> np.ndarray | None:
    """Decodifica el JPEG en memoria; la imagen se descarta al terminar el análisis."""
    if not data:
        return None
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
