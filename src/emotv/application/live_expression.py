"""Lectura en vivo de la expresión facial antes de que el estudiante la registre.

Nada de lo que pasa aquí se persiste: solo vive en memoria durante el WebSocket.
El servidor decide qué se registra con su propio último resultado estable.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from emotv.application.emotion_stabilizer import EmotionStabilizer
from emotv.domain.stabilized_emotion import StabilizedEmotion

Clock = Callable[[], float]

NO_FACE = "No se detecta un rostro. Ubica tu cara en el centro de la cámara."
NOT_STABLE = "Esperando una expresión estable."
LOW_CONFIDENCE = "La confianza del modelo es baja; mantén la expresión de forma clara."
HOLD_LONGER = "Mantén la expresión un momento más."


@dataclass(frozen=True, slots=True)
class LiveReading:
    face_detected: bool
    expression: StabilizedEmotion | None
    top: tuple[tuple[str, float], ...]
    stable_seconds: float
    blocked_reason: str | None

    @property
    def can_confirm(self) -> bool:
        return self.blocked_reason is None


class LiveExpressionTracker:
    """Sigue la expresión estabilizada y cuánto tiempo lleva sin cambiar."""

    def __init__(
        self,
        stabilizer: EmotionStabilizer | None = None,
        *,
        stable_seconds: float = 1.0,
        min_confidence: float = 0.5,
        clock: Clock = time.monotonic,
    ) -> None:
        self.stabilizer = stabilizer or EmotionStabilizer()
        self.stable_seconds = stable_seconds
        self.min_confidence = min_confidence
        self.clock = clock
        self._face = False
        self._expression: StabilizedEmotion | None = None
        self._since: float | None = None

    def update(
        self,
        prediction: tuple[str, float] | None,
        distribution: Mapping[str, float] | None = None,
    ) -> LiveReading:
        """Procesa la predicción de un frame (None si no hubo rostro)."""
        if prediction is None:
            # Sin rostro la expresión deja de contar como sostenida.
            self._face, self._expression, self._since = False, None, None
            return self._reading(())
        expression = self.stabilizer.update(*prediction)
        if expression is None:
            self._since = None
        elif self._expression is None or expression.emotion != self._expression.emotion:
            self._since = self.clock()
        self._face, self._expression = True, expression
        top = tuple(sorted(
            ((label, float(probability)) for label, probability in (distribution or {}).items()),
            key=lambda item: item[1], reverse=True,
        )[:3])
        return self._reading(top)

    def confirm(self) -> StabilizedEmotion:
        """Devuelve la expresión registrable o ValueError con el motivo del rechazo."""
        reading = self._reading(())
        if reading.blocked_reason is not None:
            raise ValueError(reading.blocked_reason)
        assert self._expression is not None
        return self._expression

    def _reading(self, top: tuple[tuple[str, float], ...]) -> LiveReading:
        held = 0.0 if self._since is None else max(0.0, self.clock() - self._since)
        if not self._face:
            reason: str | None = NO_FACE
        elif self._expression is None:
            reason = NOT_STABLE
        elif self._expression.confidence < self.min_confidence:
            reason = LOW_CONFIDENCE
        elif held < self.stable_seconds:
            reason = HOLD_LONGER
        else:
            reason = None
        return LiveReading(self._face, self._expression, top, held, reason)
