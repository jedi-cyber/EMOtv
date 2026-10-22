"""Control de calidad de la captura con cuadros sintéticos (sin rostros de personas)."""
from __future__ import annotations

import numpy as np

from emotv.domain.guided_session import QualityIssue
from emotv.infrastructure.vision.capture_quality import GuidedFrameAnalyzer, quality_issues
from emotv.infrastructure.vision.face_detection.yunet_face_detector import FaceDetection


def frame(brightness=128):
    return np.full((480, 640, 3), brightness, np.uint8)


def face(x=240, y=160, size=160, eyes=None):
    right, left = eyes or ((x + 0.3 * size, y + 0.4 * size), (x + 0.7 * size, y + 0.4 * size))
    return FaceDetection(x, y, size, size, 0.95, right_eye=right, left_eye=left)


def test_a_centered_well_lit_face_passes():
    assert quality_issues(frame(), face()) == ()


def test_each_quality_problem_is_reported():
    assert quality_issues(frame(), None) == (QualityIssue.NO_FACE,)
    assert QualityIssue.OFF_CENTER in quality_issues(frame(), face(x=10, y=10))
    assert QualityIssue.TOO_SMALL in quality_issues(frame(), face(x=300, y=220, size=40))
    assert quality_issues(frame(20), face()) == (QualityIssue.TOO_DARK,)
    assert quality_issues(frame(250), face()) == (QualityIssue.TOO_BRIGHT,)
    tilted = face(eyes=((290, 200), (350, 260)))  # línea de los ojos a 45°
    assert quality_issues(frame(), tilted) == (QualityIssue.TILTED,)


def test_the_analyzer_reports_issues_with_the_estimated_expression():
    class Detector:
        def __init__(self, found):
            self.found = found

        def detect(self, image):
            return self.found

    class Analyzer:
        def __init__(self, found):
            self.detector = Detector(found)

        def analyze_detailed(self, image):
            return ("neutral", 0.7), {"neutral": 0.7, "happiness": 0.3}

    flagged = GuidedFrameAnalyzer(Analyzer([face(x=10, y=10)])).assess(frame())
    assert flagged.issues == (QualityIssue.OFF_CENTER,) and flagged.emotion == "neutral"
    missing = GuidedFrameAnalyzer(Analyzer([])).assess(frame())
    assert missing.issues == (QualityIssue.NO_FACE,) and missing.emotion is None
