"""Detección de personas en imágenes subidas: preparación en memoria y
combinación de rostro y cuerpo, con detectores falsos (sin pesos ni fotos de
personas)."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from emotv.infrastructure.vision.person_detection import ImagePersonDetector, prepare
from emotv.infrastructure.vision.stimulus_image import InvalidStimulusImage


def encoded(width: int, height: int) -> bytes:
    image = np.full((height, width, 3), 200, np.uint8)
    cv2.rectangle(image, (width // 4, height // 4), (width // 2, height // 2), (40, 90, 160), -1)
    return cv2.imencode(".png", image)[1].tobytes()


def test_the_image_is_reduced_to_1280_pixels_per_side_in_memory():
    assert prepare(encoded(3000, 1500)).shape[:2] == (640, 1280)
    assert prepare(encoded(300, 200)).shape[:2] == (200, 300)  # no se agranda
    with pytest.raises(InvalidStimulusImage):
        prepare(b"no es una imagen")


def test_the_highest_confidence_between_face_and_body_wins():
    check = ImagePersonDetector(lambda frame: 0.3, lambda frame: 0.7)(encoded(64, 64))
    assert (check.face, check.body, check.confidence) == (0.3, 0.7, 0.7)

