"""python scripts/emotion/run_emotion_models_benchmark.py --output reports/benchmarks/ferplus-baseline.json"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import onnxruntime as ort
import psutil

from emotv.config import EMOTION_MODEL_PATH, HARDLYHUMANS_MODEL_DIR
from emotv.domain import CroppedFace
from emotv.infrastructure.vision.emotion_classifier import create_emotion_classifier
from emotv.shared.performance.model_benchmark import benchmark_predict


MODEL_WEIGHTS = {
    "ferplus_onnx": Path(EMOTION_MODEL_PATH),
    "hardlyhumans_vit": HARDLYHUMANS_MODEL_DIR / "model.safetensors",
}


def benchmark_faces(model_id: str) -> tuple[list[CroppedFace], str]:
    # Each adapter receives its native input; predict includes its preprocessing.
    if model_id not in MODEL_WEIGHTS:
        raise ValueError(f"Modelo no integrado: {model_id}")
    size = 64 if model_id == "ferplus_onnx" else 224
    shape = (16, size, size) if model_id == "ferplus_onnx" else (16, size, size, 3)
    images = np.random.default_rng(2026).integers(0, 256, shape, dtype=np.uint8)
    description = f"16 synthetic {'grayscale' if size == 64 else 'BGR color'} uint8 images, {size}x{size}, seed 2026; not accuracy evaluation"
    return [CroppedFace(image, (0, 0, size, size), 1) for image in images], description


def runtime_metadata(classifier, model_id: str) -> dict:
    if model_id == "ferplus_onnx":
        options = classifier.session.get_session_options()
        return dict(backend="onnxruntime", onnxruntime=ort.__version__,
                    providers=classifier.session.get_providers(),
                    intra_op_threads=options.intra_op_num_threads,
                    inter_op_threads=options.inter_op_num_threads)
    torch = classifier._torch
    import transformers
    return dict(backend="pytorch", device="cpu", torch=torch.__version__,
                transformers=transformers.__version__,
                intra_op_threads=torch.get_num_threads(),
                inter_op_threads=torch.get_num_interop_threads())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Línea base del clasificador facial; sin cámara ni precisión")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--min-seconds", type=float, default=3)
    parser.add_argument("--max-seconds", type=float, default=30)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", choices=tuple(MODEL_WEIGHTS), default="ferplus_onnx")
    args = parser.parse_args(argv)
    if args.runs < 1 or args.samples < 1 or args.warmup < 0 or not 0 <= args.min_seconds < args.max_seconds:
        parser.error("Parámetros de medición inválidos")
    if args.output and args.output.exists():
        parser.error("El informe ya existe; elige otra ruta para conservarlo")
    path = MODEL_WEIGHTS[args.model]
    if not path.is_file():
        parser.error(f"Pesos no instalados: {path}. Consulta docs/emotion-model-candidates.md")
    with path.open("rb") as weights:
        digest = hashlib.file_digest(weights, "sha256").hexdigest()
    process = psutil.Process()
    baseline_rss = process.memory_info().rss / 1024**2
    before = perf_counter()
    print(f"Cargando {args.model} en CPU...", flush=True)
    classifier = create_emotion_classifier(args.model)
    load_seconds = perf_counter() - before
    loaded_rss = process.memory_info().rss / 1024**2
    print(f"Carga={load_seconds:.2f}s RSS={loaded_rss:.1f} MiB", flush=True)
    faces, input_description = benchmark_faces(args.model)
    index = 0
    def predict():
        nonlocal index
        face = faces[index % len(faces)]
        index += 1
        emotion, confidence = classifier.predict(face)
        if emotion not in classifier.model.emotion_labels or not np.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Salida del clasificador inválida")
    results = []
    for run in range(args.runs):
        print(f"{args.model} corrida {run + 1}/{args.runs}", flush=True)
        result = benchmark_predict(predict, warmup=args.warmup, samples=args.samples,
            min_seconds=args.min_seconds, max_seconds=args.max_seconds)
        results.append(result)
        print(f"  media={result['inference_time_ms']:.2f} ms p95={result['p95_ms']:.2f} ms "
              f"throughput={result['fps']:.2f}/s CPU={result['cpu_percent']:.2f}% "
              f"RSS pico={result['ram_peak_mib']:.1f} MiB", flush=True)
    report = dict(schema_version=2, measured_at=datetime.now(timezone.utc).isoformat(),
        scope="predict(CroppedFace), one process, one classifier, sequential, unthrottled",
        input=input_description,
        model=dict(id=classifier.model.id, version=classifier.model.version,
                   sha256=digest, size_bytes=path.stat().st_size),
        environment=dict(os=platform.system(), os_version=platform.release(),
            architecture=platform.machine(), cpu=platform.processor(),
            logical_cpus=psutil.cpu_count(), physical_cpus=psutil.cpu_count(logical=False),
            total_ram_mib=psutil.virtual_memory().total / 1024**2,
            python=platform.python_version(), numpy=np.__version__,
            **runtime_metadata(classifier, args.model)),
        protocol=dict(runs=args.runs, samples_min=args.samples, warmup_per_run=args.warmup,
            min_seconds=args.min_seconds, max_seconds=args.max_seconds, rss_interval_ms=50),
        load=dict(seconds=load_seconds, rss_before_mib=baseline_rss,
            rss_after_mib=loaded_rss, rss_delta_mib=loaded_rss - baseline_rss),
        definitions=dict(fps="completed predictions / measured wall seconds; not browser FPS",
            cpu_process_percent="process user+system CPU / wall time *100; can exceed 100",
            cpu_percent="process CPU divided by logical CPUs; not total host utilization",
            ram="sampled whole-process RSS in MiB; includes imports/runtime; not exact model allocation",
            thread_zero="ONNX Runtime default, not zero worker threads",
            timeout="checked between predictions; cannot interrupt a hung prediction"),
        results=results)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Informe: {args.output}")
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
