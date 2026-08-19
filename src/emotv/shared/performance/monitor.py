from __future__ import annotations

import os
import time
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class PerformanceStats:
    """
    Contiene las métricas actuales de rendimiento.
    """

    fps: float
    cpu_percent: float
    ram_mb: float
    elapsed_seconds: float


class PerformanceMonitor:
    """
    Monitor ligero de rendimiento para EMOtv.

    Responsabilidades:
    - Calcular FPS.
    - Medir uso de CPU del proceso.
    - Medir consumo de RAM del proceso.
    - Registrar tiempo de ejecución.

    No debe encargarse de:
    - Mostrar información en pantalla.
    - Controlar la cámara.
    - Ejecutar inferencias.
    """

    def __init__(self, smoothing: float = 0.9) -> None:
        if not 0.0 <= smoothing < 1.0:
            raise ValueError(
                "smoothing debe estar entre 0.0 y 1.0."
            )

        self._process = psutil.Process(os.getpid())

        self._start_time = time.perf_counter()
        self._last_frame_time: float | None = None

        self._fps = 0.0
        self._smoothing = smoothing

        # Inicializa la medición de CPU.
        # La primera llamada normalmente devuelve 0.0.
        self._process.cpu_percent(interval=None)

    def update_frame(self) -> float:
        """
        Registra que se ha procesado un nuevo frame y calcula FPS.

        Se utiliza un promedio exponencial para evitar que el valor
        mostrado oscile demasiado entre fotogramas.

        Returns:
            float:
                FPS suavizados actuales.
        """
        current_time = time.perf_counter()

        if self._last_frame_time is None:
            self._last_frame_time = current_time
            return self._fps

        elapsed = current_time - self._last_frame_time
        self._last_frame_time = current_time

        if elapsed <= 0:
            return self._fps

        instantaneous_fps = 1.0 / elapsed

        if self._fps == 0.0:
            self._fps = instantaneous_fps
        else:
            self._fps = (
                self._smoothing * self._fps
                + (1.0 - self._smoothing) * instantaneous_fps
            )

        return self._fps

    def get_cpu_percent(self) -> float:
        """
        Obtiene el porcentaje de CPU usado por el proceso actual.

        Returns:
            float:
                Uso porcentual aproximado de CPU.
        """
        return self._process.cpu_percent(interval=None)

    def get_ram_mb(self) -> float:
        """
        Obtiene la memoria RAM utilizada por EMOtv.

        Returns:
            float:
                RAM utilizada en megabytes.
        """
        memory_bytes = self._process.memory_info().rss

        return memory_bytes / (1024 * 1024)

    def get_elapsed_seconds(self) -> float:
        """
        Devuelve el tiempo transcurrido desde que se creó el monitor.

        Returns:
            float:
                Segundos transcurridos.
        """
        return time.perf_counter() - self._start_time

    def get_stats(self) -> PerformanceStats:
        """
        Devuelve todas las métricas actuales agrupadas.

        Returns:
            PerformanceStats:
                FPS, CPU, RAM y tiempo de ejecución.
        """
        return PerformanceStats(
            fps=self._fps,
            cpu_percent=self.get_cpu_percent(),
            ram_mb=self.get_ram_mb(),
            elapsed_seconds=self.get_elapsed_seconds(),
        )

    def reset(self) -> None:
        """
        Reinicia las métricas temporales del monitor.
        """
        self._start_time = time.perf_counter()
        self._last_frame_time = None
        self._fps = 0.0

        self._process.cpu_percent(interval=None)