"""Nivel en vivo de un ejercicio de práctica de expresiones.

El nivel es un promedio móvil exponencial de la expresión pedida (0 a 1),
ajustado al tiempo real entre cuadros: un cuadro perdido no cambia el ritmo de
la señal. Se logra al sostener el umbral hold_seconds; un cuadro sin rostro o
con un problema de calidad no sube el nivel y reinicia el sostén.

Memoria constante: solo acumuladores (__slots__), nunca una lista de cuadros ni
de niveles. Nada se guarda en la base de datos desde aquí.
"""
from __future__ import annotations

import math

MAX_STEP_SECONDS = 2.0   # un hueco largo entre cuadros pesa como dos segundos


class PracticeTracker:
    __slots__ = ("step_index", "started_at", "hold_seconds", "relative", "threshold", "release_threshold",
                 "smoothing_seconds", "level", "peak", "above_since", "last_at", "analyzed", "flagged")

    def __init__(self, step_index: int, started_at: float, hold_seconds: float, relative: bool, *,
                 threshold: float, release_threshold: float, smoothing_seconds: float) -> None:
        self.step_index = step_index
        self.started_at = started_at          # instante (segundos) en que empezó el ejercicio
        self.hold_seconds = hold_seconds
        self.relative = relative              # el nivel se mide respecto de la base neutral
        self.threshold = threshold
        self.release_threshold = release_threshold
        self.smoothing_seconds = smoothing_seconds
        self.level = 0.0
        self.peak = 0.0
        self.above_since: float | None = None  # instante en que alcanzó el umbral
        self.last_at: float | None = None
        self.analyzed = 0                     # cuadros con rostro que actualizaron el nivel
        self.flagged = 0                      # cuadros sin rostro o con problemas de calidad

    def add(self, now: float, value: float | None) -> bool:
        """Suma un cuadro (value entre 0 y 1, o None si no sirvió). Devuelve True
        cuando la expresión pedida se sostuvo el tiempo indicado."""
        previous = self.last_at if self.last_at is not None else self.started_at
        self.last_at = now
        if value is None:
            self.flagged += 1
            self.above_since = None
            return False
        self.analyzed += 1
        elapsed = min(MAX_STEP_SECONDS, max(0.0, now - previous))
        alpha = 1.0 if self.smoothing_seconds <= 0 else 1.0 - math.exp(-elapsed / self.smoothing_seconds)
        self.level += alpha * (min(1.0, max(0.0, value)) - self.level)
        self.peak = max(self.peak, self.level)
        if self.level >= self.threshold:
            if self.above_since is None:
                self.above_since = now
        elif self.level < self.release_threshold:
            self.above_since = None
        return self.above_since is not None and now - self.above_since >= self.hold_seconds
