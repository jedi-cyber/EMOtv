"""Benchmark del contrato predict; no mide precisión ni captura de cámara."""
from collections.abc import Callable
import math
from threading import Event, Thread
from time import perf_counter

import numpy as np
import psutil


def summarize(latencies_ms: list[float], elapsed: float, cpu_seconds: float,
              logical_cpus: int, rss_samples: list[float]) -> dict:
    if not latencies_ms or elapsed <= 0 or logical_cpus < 1 or not rss_samples:
        raise ValueError("Se requieren muestras, duración y CPU válidas")
    if any(not math.isfinite(value) or value < 0 for value in latencies_ms):
        raise ValueError("Las latencias deben ser finitas y no negativas")
    raw_cpu = 100 * cpu_seconds / elapsed
    return dict(samples=len(latencies_ms), elapsed_seconds=elapsed,
        inference_time_ms=float(np.mean(latencies_ms)),
        p50_ms=float(np.percentile(latencies_ms, 50)),
        p95_ms=float(np.percentile(latencies_ms, 95)),
        min_ms=min(latencies_ms), max_ms=max(latencies_ms),
        fps=len(latencies_ms) / elapsed,
        cpu_process_percent=raw_cpu, cpu_percent=raw_cpu / logical_cpus,
        ram_mean_mib=float(np.mean(rss_samples)), ram_peak_mib=max(rss_samples),
        ram_samples=len(rss_samples))


def benchmark_predict(predict: Callable[[], object], *, warmup: int = 20,
                      samples: int = 100, min_seconds: float = 3,
                      max_seconds: float = 30) -> dict:
    if warmup < 0 or samples < 1 or not 0 <= min_seconds < max_seconds:
        raise ValueError("Parámetros de benchmark inválidos")
    process = psutil.Process()
    for _ in range(warmup):
        predict()
    rss = [process.memory_info().rss / 1024**2]
    stop = Event()
    def sample_memory():
        while not stop.wait(.05):
            rss.append(process.memory_info().rss / 1024**2)
    sampler = Thread(target=sample_memory, daemon=True)
    sampler.start()
    cpu_before = process.cpu_times()
    start = perf_counter()
    latencies = []
    try:
        while True:
            before = perf_counter()
            predict()
            now = perf_counter()
            latencies.append((now - before) * 1000)
            elapsed = now - start
            if (len(latencies) >= samples and elapsed >= min_seconds) or elapsed >= max_seconds:
                break
        cpu_after = process.cpu_times()
    finally:
        stop.set()
        sampler.join(timeout=1)
    rss.append(process.memory_info().rss / 1024**2)
    result = summarize(latencies, elapsed,
        cpu_after.user + cpu_after.system - cpu_before.user - cpu_before.system,
        psutil.cpu_count() or 1, rss)
    result["target_reached"] = len(latencies) >= samples and elapsed >= min_seconds
    return result
