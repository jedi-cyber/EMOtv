from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class CroppedFace:
    """
    Representa un rostro que ha sido recortado y preprocesado.

    Attributes:
        image: Imagen del rostro preprocesada (normalizada, en grises, etc.).
        bbox: Caja delimitadora original (x, y, width, height) con el padding aplicado.
        confidence: Confianza de la detección original.
    """

    image: np.ndarray
    bbox: tuple[int, int, int, int]
    confidence: float

    @property
    def shape(self) -> tuple[int, ...]:
        """Devuelve la forma de la imagen (alto, ancho, canales)."""
        return self.image.shape

    @property
    def is_valid(self) -> bool:
        """Verifica que la imagen no esté vacía."""
        return self.image is not None and self.image.size > 0