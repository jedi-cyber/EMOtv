"""Valida y reescribe las imágenes del banco de estímulos.

Al decodificar y volver a codificar la imagen se descartan los metadatos (EXIF,
ubicación, autor, miniaturas) y cualquier contenido que no sea la imagen misma.
"""
from __future__ import annotations

import cv2
import numpy as np

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 4096
# Firma del archivo -> (tipo, extensión con la que se vuelve a codificar).
FORMATS = (
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
)


class InvalidStimulusImage(ValueError):
    pass


def _format(data: bytes) -> tuple[str, str]:
    for signature, content_type, extension in FORMATS:
        if data.startswith(signature):
            return content_type, extension
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise InvalidStimulusImage("La imagen debe ser PNG, JPEG o WebP")


def sanitize_stimulus_image(data: bytes) -> tuple[str, bytes]:
    """Devuelve (tipo, bytes) de la imagen reescrita, o InvalidStimulusImage."""
    if not data:
        raise InvalidStimulusImage("Selecciona una imagen")
    if len(data) > MAX_BYTES:
        raise InvalidStimulusImage("La imagen supera los 5 MB")
    content_type, extension = _format(data)
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.size == 0:
        raise InvalidStimulusImage("No se pudo leer la imagen")
    height, width = image.shape[:2]
    if max(height, width) > MAX_SIDE:
        raise InvalidStimulusImage(f"La imagen supera los {MAX_SIDE} píxeles de lado")
    params = [cv2.IMWRITE_JPEG_QUALITY, 92] if extension == ".jpg" else []
    ok, encoded = cv2.imencode(extension, image, params)
    if not ok:
        raise InvalidStimulusImage("No se pudo procesar la imagen")
    return content_type, encoded.tobytes()
