from __future__ import annotations

from typing import Protocol, runtime_checkable

from emotv.domain.cropped_face import CroppedFace


@runtime_checkable
class EmotionClassifier(Protocol):
    """Puerto común para clasificadores de emociones a partir de un rostro."""

    def predict(self, cropped_face: CroppedFace) -> tuple[str, float]:
        """Devuelve la etiqueta emocional dominante y su confianza entre 0 y 1."""

        ...
