"""Verifica un benchmark local vigente y recursos del servidor antes de cargar."""
from datetime import datetime, timezone
import hashlib
import importlib.util
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform

import psutil

from emotv.application.model_admission import AdmissionLimits, evaluate_resources
from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.config import BASE_DIR, EMOTION_MODEL_PATH, HARDLYHUMANS_MODEL_DIR


class AdmissionUnavailable(ValueError):
    """Razón segura para mostrar al usuario, sin detalles internos."""


class ServerModelAdmission:
    def __init__(self, environ=None):
        env = os.environ if environ is None else environ
        self.limits = AdmissionLimits(
            warn_latency_ms=float(env.get("EMOTION_WARN_LATENCY_MS", "250")),
            block_latency_ms=float(env.get("EMOTION_BLOCK_LATENCY_MS", "1000")),
            warn_cpu_percent=float(env.get("EMOTION_WARN_CPU_PERCENT", "75")),
            block_cpu_percent=float(env.get("EMOTION_BLOCK_CPU_PERCENT", "95")),
            reserve_ram_mib=float(env.get("EMOTION_RESERVE_RAM_MIB", "512")),
            ram_safety_factor=float(env.get("EMOTION_RAM_SAFETY_FACTOR", "1.5")))
        self.max_age_days = float(env.get("EMOTION_BENCHMARK_MAX_AGE_DAYS", "30"))
        if not math.isfinite(self.max_age_days) or self.max_age_days <= 0:
            raise ValueError("Vigencia de benchmark inválida")
        self.paths = {
            "ferplus_onnx": (Path(EMOTION_MODEL_PATH), Path(env.get("FERPLUS_BENCHMARK_PATH", str(BASE_DIR / "reports/benchmarks/ferplus-baseline.json")))),
            "hardlyhumans_vit": (HARDLYHUMANS_MODEL_DIR / "model.safetensors", Path(env.get("HARDLYHUMANS_BENCHMARK_PATH", str(BASE_DIR / "reports/benchmarks/hardlyhumans-check-01.json")))),
        }
        self._hashes = {}

    def _digest(self, path):
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        if key not in self._hashes:
            with path.open("rb") as handle:
                self._hashes[key] = hashlib.file_digest(handle, "sha256").hexdigest()
        return self._hashes[key]

    def evaluate(self, model_id: str) -> dict:
        result = dict(model_id=model_id, state="BLOCKED", reasons=[])
        try:
            if model_id not in self.paths:
                raise AdmissionUnavailable("Modelo no permitido")
            weights, report_path = self.paths[model_id]
            if not weights.is_file():
                raise AdmissionUnavailable("Pesos no instalados en el servidor")
            if model_id == "hardlyhumans_vit":
                if any(importlib.util.find_spec(name) is None for name in ("torch", "transformers", "safetensors")):
                    raise ValueError("Dependencias del modelo no instaladas")
                if any(not (weights.parent / name).is_file() for name in ("config.json", "preprocessor_config.json")):
                    raise ValueError("Instalación del modelo incompleta")
            if not report_path.is_file():
                raise AdmissionUnavailable("Falta un benchmark validado; ejecuta el script de medición")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            model = report["model"]
            if model["id"] != model_id or model["version"] != EmotionModelCatalog().get(model_id).version or model["sha256"] != self._digest(weights) or model["size_bytes"] != weights.stat().st_size:
                raise ValueError("El benchmark no corresponde a los pesos instalados")
            measured = datetime.fromisoformat(report["measured_at"])
            if measured.tzinfo is None:
                raise ValueError("Benchmark sin zona horaria")
            age = (datetime.now(timezone.utc) - measured).total_seconds() / 86400
            if not 0 <= age <= self.max_age_days:
                raise AdmissionUnavailable("Benchmark vencido o con fecha futura; repite la medición")
            environment = report["environment"]
            expected = dict(os=platform.system(), architecture=platform.machine(), cpu=platform.processor(), logical_cpus=psutil.cpu_count(), python=platform.python_version())
            if any(environment.get(k) != v for k, v in expected.items()):
                raise AdmissionUnavailable("Benchmark de un entorno diferente; mide en este servidor")
            packages = ("onnxruntime",) if model_id == "ferplus_onnx" else ("torch", "transformers")
            if any(str(environment.get(package, "")).split("+")[0] != version(package).split("+")[0] for package in packages):
                raise AdmissionUnavailable("Runtime diferente al benchmark; repite la medición")
            if model_id == "hardlyhumans_vit" and environment.get("device") != "cpu":
                raise AdmissionUnavailable("Benchmark no medido con el adaptador CPU")
            runs = report["results"]
            if len(runs) < 3 or any(type(r["samples"]) is not int or r["samples"] < 100 or not math.isfinite(float(r["elapsed_seconds"])) or r["elapsed_seconds"] < 3 or r["target_reached"] is not True for r in runs):
                raise AdmissionUnavailable("Benchmark insuficiente: requiere 3 corridas, 100 muestras y 3 segundos cada una")
            latencies = [float(r["p95_ms"]) for r in runs]
            memory = [float(r["ram_peak_mib"]) for r in runs]
            if any(not math.isfinite(v) or v <= 0 for v in latencies + memory):
                raise ValueError("Benchmark con métricas inválidas")
            p95, peak = max(latencies), max(memory)
            # A fresh bounded CPU sample; avoid psutil's uninitialized zero reading.
            cpu = psutil.cpu_percent(interval=0.1)
            available = psutil.virtual_memory().available / 1024**2
            result.update(evaluate_resources(p95_ms=p95, peak_ram_mib=peak,
                          available_ram_mib=available, cpu_percent=cpu, limits=self.limits))
            result["metrics"] = dict(p95_ms=p95, peak_ram_mib=peak,
                                     available_ram_mib=available, cpu_percent=cpu)
        except AdmissionUnavailable as error:
            result["reasons"] = [str(error)]
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, ImportError):
            # No filesystem paths, secrets or traceback exposed to the browser.
            result["reasons"] = ["Evaluación ausente, inválida o no vigente; revisa instalación y benchmark en el servidor"]
        return result
