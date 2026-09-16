from __future__ import annotations

import numpy as np

from emotv.domain.cropped_face import CroppedFace
from emotv.application.ports.emotion_classifier import EmotionClassifier
from emotv.infrastructure.vision.emotion_classifier.factory import create_emotion_classifier
from emotv.infrastructure.vision.face_detection.yunet_face_detector import (
    YuNetFaceDetector,
)
from emotv.infrastructure.vision.face_processing.face_preprocessor import (
    FacePreprocessor,
)


class EmotionFrameAnalyzer:
    """Convierte un frame BGR en una predicción facial cuando detecta un rostro."""

    def __init__(
        self,
        detector: YuNetFaceDetector | None = None,
        preprocessor: FacePreprocessor | None = None,
        classifier: EmotionClassifier | None = None,
    ) -> None:
        self.detector = detector or YuNetFaceDetector()
        self.classifier = classifier if classifier is not None else create_emotion_classifier()
        self.preprocessor = preprocessor if preprocessor is not None else FacePreprocessor(**getattr(self.classifier, "face_preprocessor_options", {}))

    def analyze(self, frame: np.ndarray) -> tuple[str, float] | None:
        detections = self.detector.detect(frame)
        if not detections:
            return None
        face: CroppedFace | None = self.preprocessor.process(frame, detections[0])
        if face is None or not face.is_valid:
            return None
        return self.classifier.predict(face)
