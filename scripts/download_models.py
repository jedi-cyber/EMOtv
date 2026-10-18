"""Descarga y verifica los pesos necesarios para arrancar EMOtv.

Uso:
    python scripts/download_models.py                 # descarga lo que falte
    python scripts/download_models.py --check         # solo verifica, no descarga
    python scripts/download_models.py --include-experimental
    python scripts/download_models.py --ensure-benchmark models/weights/benchmarks/ferplus.json         --ensure-hsemotion-benchmark models/weights/benchmarks/hsemotion.json

Es idempotente: si un archivo ya existe con el SHA-256 esperado no se descarga.
Un archivo con hash distinto se reemplaza (o se informa con --check).
HSEmotion (lectura en vivo predeterminada) se descarga siempre, pero es
opcional: si falta o su benchmark no es válido, la API usa FER+.
hardlyhumans_vit solo se descarga con --include-experimental y requiere el
extra opcional emotion-vit.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from emotv.config import (  # noqa: E402
    EMOTION_MODEL_PATH,
    HARDLYHUMANS_MODEL_DIR,
    HSEMOTION_MODEL_PATH,
    HSEMOTION_MODEL_URL,
    POSE_MODEL_PATH,
    POSE_MODEL_URL,
    YUNET_PATH,
)


@dataclass(frozen=True)
class ModelWeight:
    name: str
    url: str
    path: Path
    sha256: str


REQUIRED_WEIGHTS = (
    # Mismo archivo que publica opencv_zoo con este nombre (commit 26cc381, 2026-05-22).
    ModelWeight(
        "YuNet",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
        "face_detection_yunet_2026may.onnx",
        YUNET_PATH,
        "ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0",
    ),
    ModelWeight(
        "FER+",
        "https://huggingface.co/onnxmodelzoo/emotion-ferplus-8/resolve/main/emotion-ferplus-8.onnx",
        EMOTION_MODEL_PATH,
        "a2a2ba6a335a3b29c21acb6272f962bd3d47f84952aaffa03b60986e04efa61c",
    ),
    ModelWeight(
        "MediaPipe Pose Landmarker Lite",
        POSE_MODEL_URL,
        POSE_MODEL_PATH,
        "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
    ),
)

# Opcionales: un fallo se informa, pero no impide arrancar (la API usa FER+).
OPTIONAL_WEIGHTS = (
    # sb-ai-lab/EmotiEffLib (antes HSE-asavchenko/face-emotion-recognition),
    # archivo fijado al commit af83348 (2022-11-09).
    ModelWeight(
        "HSEmotion enet_b0_8_best_afew",
        HSEMOTION_MODEL_URL,
        HSEMOTION_MODEL_PATH,
        "7aa2ea31c1311f4f8aa9d3fdb085d418dd4e7a48c4b9ed41df8c044f91d0213f",
    ),
)


def sha256_of(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def is_valid(weight: ModelWeight) -> bool:
    return weight.path.is_file() and sha256_of(weight.path) == weight.sha256


def download(weight: ModelWeight, *, attempts: int = 4) -> None:
    weight.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = weight.path.with_name(weight.path.name + ".download")
    try:
        for attempt in range(1, attempts + 1):
            try:
                urllib.request.urlretrieve(weight.url, temporary)
                break
            except (OSError, urllib.error.URLError) as error:
                if attempt == attempts:
                    raise
                print(f"  intento {attempt} fallido ({error}); reintentando...")
                time.sleep(2 * attempt)
        digest = sha256_of(temporary)
        if digest != weight.sha256:
            raise RuntimeError(f"{weight.name}: SHA-256 inesperado ({digest})")
        temporary.replace(weight.path)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_weights(*, check_only: bool = False, weights=None) -> list[str]:
    """Devuelve los nombres de los pesos que siguen faltando o son inválidos."""

    problems = []
    for weight in REQUIRED_WEIGHTS if weights is None else weights:
        if is_valid(weight):
            print(f"[ok] {weight.name}")
            continue
        if check_only:
            print(f"[falta] {weight.name}: ausente o con hash distinto")
            problems.append(weight.name)
            continue
        print(f"[descargando] {weight.name}")
        try:
            download(weight)
            print(f"[ok] {weight.name}")
        except (OSError, RuntimeError, urllib.error.URLError) as error:
            print(f"[error] {weight.name}: {error}")
            problems.append(weight.name)
    return problems


# Modelo -> (nombre legible, variable de entorno con la ruta del informe).
BENCHMARKED_MODELS = {
    "ferplus_onnx": ("FER+", "FERPLUS_BENCHMARK_PATH"),
    "hsemotion_enet_b0_8_best_afew": ("HSEmotion", "HSEMOTION_BENCHMARK_PATH"),
}


def benchmark_is_current(report: Path, model_id: str = "ferplus_onnx") -> bool:
    """Usa la misma admisión que la API: el informe debe ser de este entorno y vigente."""

    from emotv.infrastructure.vision.emotion_classifier.model_admission import ServerModelAdmission

    environ = {**os.environ, BENCHMARKED_MODELS[model_id][1]: str(report)}
    # "metrics" solo aparece si el informe superó todas las comprobaciones;
    # un bloqueo por CPU o RAM momentáneos no exige volver a medir.
    return "metrics" in ServerModelAdmission(environ).evaluate(model_id)


def ensure_benchmark(report: Path, model_id: str = "ferplus_onnx") -> None:
    name = BENCHMARKED_MODELS[model_id][0]
    if benchmark_is_current(report, model_id):
        print(f"[ok] benchmark {name} vigente para este entorno")
        return
    from scripts.emotion.run_emotion_models_benchmark import main as run_benchmark

    print(f"[midiendo] benchmark {name} en este entorno (requisito de admisión del modelo)")
    staged = report.with_name(report.name + ".new")
    staged.unlink(missing_ok=True)
    if run_benchmark(["--model", model_id, "--output", str(staged)]) != 0:
        raise RuntimeError("La medición del benchmark falló")
    staged.replace(report)
    if not benchmark_is_current(report, model_id):
        raise RuntimeError("El benchmark medido no supera la validación de admisión")
    print(f"[ok] benchmark {name} medido")


def ensure_experimental() -> None:
    if HARDLYHUMANS_MODEL_DIR.exists():
        print("[ok] hardlyhumans_vit (experimental) ya instalado")
        return
    from scripts.emotion.download_hardlyhumans_model import download_model

    print("[descargando] hardlyhumans_vit (experimental)")
    download_model()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Solo verificar; no descargar")
    parser.add_argument("--include-experimental", action="store_true",
                        help="Descargar también hardlyhumans_vit (opcional)")
    parser.add_argument("--ensure-benchmark", type=Path, metavar="INFORME",
                        help="Medir el benchmark FER+ en este entorno si el informe falta o no es vigente")
    parser.add_argument("--ensure-hsemotion-benchmark", type=Path, metavar="INFORME",
                        help="Igual para HSEmotion; si falla, la API usará FER+")
    args = parser.parse_args(argv)

    problems = ensure_weights(check_only=args.check)
    optional_missing = ensure_weights(check_only=args.check, weights=OPTIONAL_WEIGHTS)
    if optional_missing:
        print("[aviso] Opcionales pendientes (la lectura en vivo usará FER+): " + ", ".join(optional_missing))
    if args.include_experimental and not args.check:
        ensure_experimental()
    if args.ensure_benchmark and not problems and not args.check:
        ensure_benchmark(args.ensure_benchmark)
    if args.ensure_hsemotion_benchmark and not optional_missing and not args.check:
        try:
            ensure_benchmark(args.ensure_hsemotion_benchmark, "hsemotion_enet_b0_8_best_afew")
        except RuntimeError as error:
            print(f"[aviso] HSEmotion sin benchmark válido ({error}); la lectura en vivo usará FER+")
    if problems:
        print("Pesos pendientes: " + ", ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
