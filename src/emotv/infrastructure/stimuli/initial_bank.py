"""Dibujos del banco inicial: caras esquemáticas de creación propia, generadas en
memoria. No son fotos de personas ni se basan en ninguna; cada emoción tiene
tres variantes (color de piel y cabello) para que el reconocimiento no dependa
de un solo dibujo. Se dibujan con OpenCV y se entregan como PNG."""
from __future__ import annotations

from collections.abc import Iterator

import cv2
import numpy as np

from emotv.application.stimulus_service import InitialDrawing

SIZE = 512
CENTER = (256, 270)
RADIUS = 190
INK = (40, 40, 40)            # BGR
LINE = 10
BACKGROUND = (246, 240, 232)

# Variantes: color de la cara y del cabello (None: sin cabello).
VARIANTS = (
    ((90, 205, 255), None),                 # amarilla
    ((150, 190, 235), (40, 50, 90)),        # piel clara, cabello castaño
    ((70, 110, 165), (25, 25, 30)),         # piel morena, cabello negro
)

TITLES = {
    "happiness": "Alegría", "sadness": "Tristeza", "anger": "Enojo",
    "fear": "Miedo", "surprise": "Sorpresa", "disgust": "Asco",
}


def _point(dx: float, dy: float) -> tuple[int, int]:
    return int(CENTER[0] + dx), int(CENTER[1] + dy)


def _brow(image, x: int, inner_dy: int, outer_dy: int) -> None:
    """Ceja sobre el ojo en x (negativo: izquierdo). inner/outer: altura del extremo interior y exterior."""
    side = -1 if x < 0 else 1
    cv2.line(image, _point(x - side * 10, -70 + inner_dy), _point(x + side * 45, -70 + outer_dy), INK, LINE,
             cv2.LINE_AA)


def _eyes(image, kind: str) -> None:
    for x in (-70, 70):
        if kind == "wide":
            cv2.circle(image, _point(x, -20), 30, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(image, _point(x, -20), 30, INK, 6, cv2.LINE_AA)
            cv2.circle(image, _point(x, -20), 11, INK, -1, cv2.LINE_AA)
        elif kind == "happy":
            cv2.ellipse(image, _point(x, -10), (28, 22), 0, 200, 340, INK, LINE, cv2.LINE_AA)
        elif kind == "squint":
            cv2.line(image, _point(x - 25, -18), _point(x + 25, -18), INK, LINE, cv2.LINE_AA)
        else:
            cv2.circle(image, _point(x, -18), 17, INK, -1, cv2.LINE_AA)


def _features(image, expression: str) -> None:
    if expression == "happiness":
        _eyes(image, "happy")
        cv2.ellipse(image, _point(0, 35), (95, 70), 0, 15, 165, INK, LINE, cv2.LINE_AA)
        for x in (-115, 115):
            cv2.circle(image, _point(x, 40), 22, (150, 150, 245), -1, cv2.LINE_AA)
    elif expression == "sadness":
        _eyes(image, "dot")
        _brow(image, -70, -18, 10)
        _brow(image, 70, -18, 10)
        cv2.ellipse(image, _point(0, 120), (70, 45), 0, 200, 340, INK, LINE, cv2.LINE_AA)
        cv2.ellipse(image, _point(-72, 30), (11, 20), 0, 0, 360, (230, 160, 70), -1, cv2.LINE_AA)
    elif expression == "anger":
        _eyes(image, "dot")
        _brow(image, -70, 22, -12)
        _brow(image, 70, 22, -12)
        cv2.ellipse(image, _point(0, 125), (60, 30), 0, 200, 340, INK, LINE, cv2.LINE_AA)
    elif expression == "fear":
        _eyes(image, "wide")
        _brow(image, -70, -28, -12)
        _brow(image, 70, -28, -12)
        points = np.array([_point(x, 95 + (8 if i % 2 else -8)) for i, x in enumerate(range(-60, 61, 20))])
        cv2.polylines(image, [points], False, INK, LINE, cv2.LINE_AA)
    elif expression == "surprise":
        _eyes(image, "wide")
        for x in (-70, 70):
            cv2.ellipse(image, _point(x, -60), (38, 22), 0, 200, 340, INK, LINE, cv2.LINE_AA)
        cv2.ellipse(image, _point(0, 100), (32, 42), 0, 0, 360, INK, LINE, cv2.LINE_AA)
    elif expression == "disgust":
        _eyes(image, "squint")
        _brow(image, -70, 18, 5)
        _brow(image, 70, -10, -20)
        cv2.line(image, _point(-18, 40), _point(-6, 52), INK, 6, cv2.LINE_AA)
        cv2.line(image, _point(18, 40), _point(6, 52), INK, 6, cv2.LINE_AA)
        points = np.array([_point(-65, 110), _point(-25, 95), _point(15, 115), _point(65, 95)])
        cv2.polylines(image, [points], False, INK, LINE, cv2.LINE_AA)
        cv2.ellipse(image, _point(0, 115), (22, 26), 0, 0, 180, (120, 110, 235), -1, cv2.LINE_AA)
    else:
        raise ValueError(f"Expresión sin dibujo: {expression}")


def draw(expression: str, variant: int) -> bytes:
    """Una cara esquemática como PNG. variant va de 0 a 2."""
    skin, hair = VARIANTS[variant]
    image = np.full((SIZE, SIZE, 3), BACKGROUND, dtype=np.uint8)
    if hair is not None:
        cv2.ellipse(image, _point(0, -40), (RADIUS + 18, RADIUS + 10), 0, 180, 360, hair, -1, cv2.LINE_AA)
    cv2.circle(image, CENTER, RADIUS, skin, -1, cv2.LINE_AA)
    cv2.circle(image, CENTER, RADIUS, INK, 6, cv2.LINE_AA)
    if hair is not None:
        # Flequillo: cubre la parte alta de la cara hasta la frente.
        cv2.ellipse(image, _point(0, -95), (RADIUS - 12, 118), 0, 180, 360, hair, -1, cv2.LINE_AA)
    _features(image, expression)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("No se pudo generar el dibujo")
    return encoded.tobytes()


def initial_drawings() -> Iterator[InitialDrawing]:
    """Seis emociones básicas, tres variantes cada una, en orden estable."""
    for expression, name in TITLES.items():
        for variant in range(len(VARIANTS)):
            yield InitialDrawing(title=f"{name} {variant + 1}", expected_expression=expression,
                                 image=draw(expression, variant))
