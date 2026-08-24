from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import psutil


@dataclass(frozen=True)
class PerformanceStats:
    """
    Contiene las métricas actuales de rendimiento.
    """

    fps: float
    cpu_percent: float          # Uso de CPU del proceso relativo al total (0-100%)
    ram_mb: float
    elapsed_seconds: float


@dataclass
class PerformanceSummary:
    """
    Resumen de rendimiento durante un período de medición.
    """
    fps_avg: float
    fps_min: float
    fps_max: float
    cpu_avg: float
    ram_avg_mb: float
    ram_max_mb: float
    duration_seconds: float


class PerformanceMonitor:
    """
    Monitor ligero de rendimiento para EMOtv.

    Responsabilidades:
    - Calcular FPS suavizados y estadísticas (min, max, avg).
    - Medir uso de CPU del proceso (relativo al total y crudo).
    - Medir consumo de RAM del proceso.
    - Registrar tiempo de ejecución.
    - Proporcionar resúmenes periódicos.

    No debe encargarse de:
    - Mostrar información en pantalla.
    - Controlar la cámara.
    - Ejecutar inferencias.
    """

    def __init__(
        self,
        smoothing: float = 0.9,
        history_size: int = 60,  # para calcular estadísticas sobre los últimos N frames
    ) -> None:
        if not 0.0 <= smoothing < 1.0:
            raise ValueError("smoothing debe estar entre 0.0 y 1.0.")
        if history_size < 2:
            raise ValueError("history_size debe ser al menos 2.")

        self._process = psutil.Process(os.getpid())
        self._cpu_count = psutil.cpu_count() or 1  # evitar división por cero

        self._start_time = time.perf_counter()
        self._last_frame_time: Optional[float] = None

        self._fps = 0.0
        self._smoothing = smoothing

        # Historial para estadísticas
        self._fps_history: deque[float] = deque(maxlen=history_size)
        self._cpu_history: deque[float] = deque(maxlen=history_size)
        self._ram_history: deque[float] = deque(maxlen=history_size)

        # Inicializa la medición de CPU (primera llamada suele devolver 0.0)
        self._process.cpu_percent(interval=None)

    def update_frame(self) -> float:
        """
        Registra que se ha procesado un nuevo frame y calcula FPS suavizado.

        También almacena el valor en el historial para estadísticas posteriores.

        Returns:
            float: FPS suavizados actuales.
        """
        current_time = time.perf_counter()

        if self._last_frame_time is None:
            self._last_frame_time = current_time
            # Almacenamos el FPS inicial (0) pero no lo añadimos al historial aún
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

        # Guardamos el FPS suavizado en el historial (para estadísticas)
        self._fps_history.append(self._fps)

        # También almacenamos CPU y RAM en cada frame para tener estadísticas
        self._cpu_history.append(self.get_cpu_percent())
        self._ram_history.append(self.get_ram_mb())

        return self._fps

    def get_cpu_percent(self) -> float:
        """
        Obtiene el porcentaje de CPU usado por el proceso actual,
        relativo al total del sistema (0‑100 %).

        Es el valor recomendado para mostrar en la interfaz de usuario.

        Returns:
            float: Uso de CPU en porcentaje (0‑100).
        """
        raw = self._process.cpu_percent(interval=None)
        return raw / self._cpu_count

    def get_cpu_percent_raw(self) -> float:
        """
        Obtiene el porcentaje de CPU sin normalizar (puede superar 100 %
        si el proceso usa varios núcleos). Útil para logs internos.

        Returns:
            float: Uso de CPU crudo (puede ser > 100 %).
        """
        return self._process.cpu_percent(interval=None)

    def get_system_cpu_percent(self) -> float:
        """
        Obtiene el porcentaje de uso total de la CPU del sistema (0‑100 %).

        Returns:
            float: Uso global de CPU.
        """
        return psutil.cpu_percent(interval=None)

    def get_ram_mb(self) -> float:
        """
        Obtiene la memoria RAM utilizada por EMOtv.

        Returns:
            float: RAM utilizada en megabytes.
        """
        memory_bytes = self._process.memory_info().rss
        return memory_bytes / (1024 * 1024)

    def get_elapsed_seconds(self) -> float:
        """
        Devuelve el tiempo transcurrido desde que se creó el monitor.

        Returns:
            float: Segundos transcurridos.
        """
        return time.perf_counter() - self._start_time

    def get_stats(self) -> PerformanceStats:
        """
        Devuelve todas las métricas actuales agrupadas.

        Returns:
            PerformanceStats: FPS, CPU (relativo), RAM y tiempo de ejecución.
        """
        return PerformanceStats(
            fps=self._fps,
            cpu_percent=self.get_cpu_percent(),
            ram_mb=self.get_ram_mb(),
            elapsed_seconds=self.get_elapsed_seconds(),
        )

    def get_summary(self) -> PerformanceSummary:
        """
        Calcula un resumen estadístico basado en el historial de frames.

        Returns:
            PerformanceSummary: promedios, mínimos, máximos de FPS, CPU y RAM.
        """
        if len(self._fps_history) == 0:
            # Si aún no hay datos, devolvemos valores por defecto
            return PerformanceSummary(
                fps_avg=0.0,
                fps_min=0.0,
                fps_max=0.0,
                cpu_avg=0.0,
                ram_avg_mb=0.0,
                ram_max_mb=0.0,
                duration_seconds=self.get_elapsed_seconds(),
            )

        return PerformanceSummary(
            fps_avg=sum(self._fps_history) / len(self._fps_history),
            fps_min=min(self._fps_history),
            fps_max=max(self._fps_history),
            cpu_avg=sum(self._cpu_history) / len(self._cpu_history),
            ram_avg_mb=sum(self._ram_history) / len(self._ram_history),
            ram_max_mb=max(self._ram_history),
            duration_seconds=self.get_elapsed_seconds(),
        )

    def reset(self) -> None:
        """
        Reinicia todas las métricas temporales y el historial.
        """
        self._start_time = time.perf_counter()
        self._last_frame_time = None
        self._fps = 0.0
        self._fps_history.clear()
        self._cpu_history.clear()
        self._ram_history.clear()

        self._process.cpu_percent(interval=None)