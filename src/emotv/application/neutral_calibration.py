"""Calibración neutral opcional de la lectura en vivo.

El estudiante mantiene el rostro relajado unos segundos; el promedio de la
distribución del modelo en ese tiempo es su base. Después, cada clase se
compara con esa base y la sugerencia es la clase que más aumentó.

La base vive solo en memoria, durante una conexión del WebSocket: no se
guarda en la base de datos ni se envía a otro servicio. No cambia lo que se
registra ni el umbral de registro.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

Clock = Callable[[], float]

NOT_CALIBRATED, CALIBRATING, CALIBRATED = "none", "calibrating", "calibrated"
CALIBRATION_FAILED = (
    "No se vio tu rostro el tiempo suficiente para calibrar. "
    "Mira a la cámara con el rostro relajado y vuelve a intentarlo."
)


@dataclass(frozen=True, slots=True)
class CalibratedClass:
    emotion: str
    probability: float
    baseline: float

    @property
    def change(self) -> float:
        """Cambio respecto a la base, en proporción (0.25 = 25 puntos)."""
        return self.probability - self.baseline


class NeutralCalibration:
    """Base neutral promedio de una conexión; nada se persiste."""

    def __init__(
        self,
        *,
        seconds: float = 3.0,
        min_increase: float = 0.10,
        min_samples: int = 5,
        clock: Clock = time.monotonic,
    ) -> None:
        if seconds <= 0 or min_samples < 1 or not 0.0 <= min_increase <= 1.0:
            raise ValueError("Parámetros de calibración inválidos")
        self.seconds = seconds
        self.min_increase = min_increase
        self.min_samples = min_samples
        self.clock = clock
        self.state = NOT_CALIBRATED
        self._baseline: dict[str, float] | None = None
        self._samples: list[Mapping[str, float]] = []
        self._started: float | None = None

    @property
    def progress(self) -> float:
        if self.state == CALIBRATED:
            return 1.0
        if self._started is None:
            return 0.0
        return min(1.0, max(0.0, (self.clock() - self._started) / self.seconds))

    def start(self) -> None:
        """Empieza (o repite) la calibración; descarta la base anterior."""
        self.state, self._baseline, self._samples, self._started = CALIBRATING, None, [], self.clock()

    def add(self, distribution: Mapping[str, float] | None) -> str | None:
        """Suma un frame (None si no hubo rostro). Devuelve un aviso si la calibración falla."""
        if self.state != CALIBRATING:
            return None
        if distribution:
            self._samples.append(dict(distribution))
        if self.progress < 1.0:
            return None
        samples, self._samples, self._started = self._samples, [], None
        if len(samples) < self.min_samples:
            self.state = NOT_CALIBRATED
            return CALIBRATION_FAILED
        labels = {label for sample in samples for label in sample}
        self._baseline = {label: sum(float(sample.get(label, 0.0)) for sample in samples) / len(samples)
                          for label in labels}
        self.state = CALIBRATED
        return None

    def compare(self, distribution: Mapping[str, float]) -> tuple[tuple[CalibratedClass, ...], str | None]:
        """Clases ordenadas por probabilidad con su cambio, y la expresión sugerida.

        La sugerida es la de mayor aumento respecto a la base, aunque no sea la
        más probable, siempre que ese aumento alcance min_increase.
        """
        if self._baseline is None:
            raise ValueError("Sin calibración")
        labels = set(distribution) | set(self._baseline)
        classes = tuple(sorted(
            (CalibratedClass(label, float(distribution.get(label, 0.0)), self._baseline.get(label, 0.0))
             for label in labels),
            key=lambda item: item.probability, reverse=True,
        ))
        best = max(classes, key=lambda item: item.change, default=None)
        suggested = best.emotion if best is not None and best.change >= self.min_increase else None
        return classes, suggested
