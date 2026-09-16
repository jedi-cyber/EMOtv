"""Política pura de admisión: límites operativos, no medidas de precisión."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AdmissionLimits:
    warn_latency_ms: float = 250
    block_latency_ms: float = 1000
    warn_cpu_percent: float = 75
    block_cpu_percent: float = 95
    reserve_ram_mib: float = 512
    ram_safety_factor: float = 1.5

    def __post_init__(self):
        values = tuple(vars(self).values())
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Límites de admisión inválidos")
        if self.warn_latency_ms >= self.block_latency_ms or not self.warn_cpu_percent < self.block_cpu_percent <= 100 or self.ram_safety_factor < 1:
            raise ValueError("Los límites de advertencia deben preceder al bloqueo")


def evaluate_resources(*, p95_ms: float, peak_ram_mib: float,
                       available_ram_mib: float, cpu_percent: float,
                       limits: AdmissionLimits) -> dict:
    values = (p95_ms, peak_ram_mib, available_ram_mib, cpu_percent)
    if any(not math.isfinite(v) or v < 0 for v in values) or peak_ram_mib <= 0 or cpu_percent > 100:
        return dict(state="BLOCKED", reasons=["Mediciones de recursos inválidas"])
    required = peak_ram_mib * limits.ram_safety_factor + limits.reserve_ram_mib
    blocked, warnings = [], []
    if p95_ms >= limits.block_latency_ms:
        blocked.append("Latencia p95 supera el límite permitido")
    elif p95_ms >= limits.warn_latency_ms:
        warnings.append("Latencia elevada: el análisis puede responder lentamente")
    if available_ram_mib < required:
        blocked.append("RAM disponible insuficiente para iniciar otra instancia")
    elif available_ram_mib < required * 1.5:
        warnings.append("Margen de RAM reducido")
    if cpu_percent >= limits.block_cpu_percent:
        blocked.append("Servidor saturado: CPU por encima del límite")
    elif cpu_percent >= limits.warn_cpu_percent:
        warnings.append("Carga de CPU elevada en el servidor")
    return dict(state="BLOCKED" if blocked else "WARNING" if warnings else "SUPPORTED",
                reasons=blocked + warnings, required_ram_mib=required)
