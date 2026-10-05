"""Descarga y verifica los pesos necesarios para arrancar EMOtv.

Uso:
    python scripts/download_models.py                 # descarga lo que falte
    python scripts/download_models.py --check         # solo verifica, no descarga
    python scripts/download_models.py --include-experimental
    python scripts/download_models.py --ensure-benchmark models/weights/benchmarks/ferplus.json

Es idempotente: si un archivo ya existe con el SHA-256 esperado no se descarga.
Un archivo con hash distinto se reemplaza (o se informa con --check).
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


def ensure_weights(*, check_only: bool = False) -> list[str]:
    """Devuelve los nombres de los pesos que siguen faltando o son inválidos."""

    problems = []
    for weight in REQUIRED_WEIGHTS:
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


def benchmark_is_current(report: Path) -> bool:
    """Usa la misma admisión que la API: el informe debe ser de este entorno y vigente."""

    from emotv.infrastructure.vision.emotion_classifier.model_admission import ServerModelAdmission

    environ = {**os.environ, "FERPLUS_BENCHMARK_PATH": str(report)}
    # "metrics" solo aparece si el informe superó todas las comprobaciones;
    # un bloqueo por CPU o RAM momentáneos no exige volver a medir.
    return "metrics" in ServerModelAdmission(environ).evaluate("ferplus_onnx")


def ensure_benchmark(report: Path) -> None:
    if benchmark_is_current(report):
        print("[ok] benchmark FER+ vigente para este entorno")
        return
    from scripts.emotion.run_emotion_models_benchmark import main as run_benchmark

    print("[midiendo] benchmark FER+ en este entorno (requisito de admisión del modelo)")
    staged = report.with_name(report.name + ".new")
    staged.unlink(missing_ok=True)
    if run_benchmark(["--model", "ferplus_onnx", "--output", str(staged)]) != 0:
        raise RuntimeError("La medición del benchmark falló")
    staged.replace(report)
    if not benchmark_is_current(report):
        raise RuntimeError("El benchmark medido no supera la validación de admisión")
    print("[ok] benchmark FER+ medido")


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
    args = parser.parse_args(argv)

    problems = ensure_weights(check_only=args.check)
    if args.include_experimental and not args.check:
        ensure_experimental()
    if args.ensure_benchmark and not problems and not args.check:
        ensure_benchmark(args.ensure_benchmark)
    if problems:
        print("Pesos pendientes: " + ", ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
