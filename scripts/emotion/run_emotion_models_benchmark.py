"""python scripts/emotion/run_emotion_models_benchmark.py --output reports/benchmarks/ferplus-baseline.json

Mide dos cosas, en un solo proceso:
- predict(CroppedFace) con la entrada nativa del modelo (lo que usa la admisión);
- el cuadro completo de la lectura en vivo con 1, 2 y 4 sesiones simultáneas:
  JPEG de 640x480, decodificación, YuNet, recorte y clasificación, cada sesión
  con su propio analizador, como en el servidor.
Las imágenes son sintéticas y viven solo en memoria: no se guarda ninguna.
La medición concurrente es informativa: no cambia el modelo ni bloquea nada.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cv2
import numpy as np
import onnxruntime as ort
import psutil

from emotv.config import EMOTION_MODEL_PATH, HARDLYHUMANS_MODEL_DIR, HSEMOTION_MODEL_PATH
from emotv.domain import CroppedFace
from emotv.infrastructure.vision.emotion_classifier import create_emotion_classifier
from emotv.infrastructure.vision.face_detection.yunet_face_detector import FaceDetection, YuNetFaceDetector
from emotv.infrastructure.vision.face_processing.face_preprocessor import FacePreprocessor
from emotv.shared.performance.model_benchmark import benchmark_concurrent, benchmark_predict


MODEL_WEIGHTS = {
    "ferplus_onnx": Path(EMOTION_MODEL_PATH),
    "hsemotion_enet_b0_8_best_afew": Path(HSEMOTION_MODEL_PATH),
    "hardlyhumans_vit": HARDLYHUMANS_MODEL_DIR / "model.safetensors",
}
FRAME_SIZE = (640, 480)
# Misma calidad JPEG que envía el analizador web (canvas.toBlob(..., .72)).
JPEG_QUALITY = 72
# Si YuNet no encuentra un rostro en el cuadro sintético, se recorta esta caja
# central para que el recorte y la clasificación también cuenten en el tiempo.
FALLBACK_FACE = FaceDetection(220, 140, 200, 200, 1.0)
CONCURRENT_SESSIONS = (1, 2, 4)
create_face_detector = YuNetFaceDetector


def benchmark_faces(model_id: str) -> tuple[list[CroppedFace], str]:
    # Each adapter receives its native input; predict includes its preprocessing.
    if model_id not in MODEL_WEIGHTS:
        raise ValueError(f"Modelo no integrado: {model_id}")
    size = 64 if model_id == "ferplus_onnx" else 224
    shape = (16, size, size) if model_id == "ferplus_onnx" else (16, size, size, 3)
    images = np.random.default_rng(2026).integers(0, 256, shape, dtype=np.uint8)
    description = f"16 synthetic {'grayscale' if size == 64 else 'BGR color'} uint8 images, {size}x{size}, seed 2026; not accuracy evaluation"
    return [CroppedFace(image, (0, 0, size, size), 1) for image in images], description


def synthetic_frame_jpeg(seed: int = 2026) -> bytes:
    """Cuadro BGR sintético de 640x480 codificado en JPEG, solo en memoria."""
    width, height = FRAME_SIZE
    frame = np.random.default_rng(seed).integers(0, 256, (height, width, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise RuntimeError("No se pudo codificar el cuadro sintético")
    return encoded.tobytes()


def frame_step(jpeg: bytes, detector, preprocessor, classifier):
    """Un cuadro de la lectura en vivo: decodificación, YuNet, recorte y clasificación."""
    labels = classifier.model.emotion_labels

    def step():
        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("No se pudo decodificar el cuadro")
        detections = detector.detect(frame)
        face = preprocessor.process(frame, detections[0] if detections else FALLBACK_FACE)
        if face is None or not face.is_valid:
            raise ValueError("Recorte vacío")
        emotion, confidence = classifier.predict(face)
        if emotion not in labels or not np.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Salida del clasificador inválida")
    return step


def session_step(model_id: str, threads: int, seed: int):
    """Una sesión como la del servidor: analizador propio y su cuadro sintético."""
    classifier = create_emotion_classifier(model_id, intra_op_threads=threads)
    preprocessor = FacePreprocessor(**getattr(classifier, "face_preprocessor_options", {}))
    return frame_step(synthetic_frame_jpeg(seed), create_face_detector(), preprocessor, classifier)


def runtime_metadata(classifier, model_id: str) -> dict:
    if model_id != "hardlyhumans_vit":
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
    parser.add_argument("--threads", type=int, default=1,
                        help="Hilos de onnxruntime por sesión en la medición concurrente (ONNX_THREADS_PER_SESSION)")
    parser.add_argument("--frame-samples", type=int, default=50,
                        help="Cuadros por sesión en la medición concurrente")
    args = parser.parse_args(argv)
    if args.runs < 1 or args.samples < 1 or args.warmup < 0 or not 0 <= args.min_seconds < args.max_seconds:
        parser.error("Parámetros de medición inválidos")
    if args.threads < 1 or args.frame_samples < 1:
        parser.error("--threads y --frame-samples deben ser al menos 1")
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
    concurrent = {}
    for sessions in CONCURRENT_SESSIONS:
        steps = [session_step(args.model, args.threads, 2026 + number) for number in range(sessions)]
        print(f"{args.model} cuadro completo con {sessions} sesión(es) simultánea(s)", flush=True)
        result = benchmark_concurrent(steps, warmup=min(args.warmup, 5),
                                      samples_per_session=args.frame_samples, max_seconds=args.max_seconds * 2)
        concurrent[str(sessions)] = result
        print(f"  p50={result['p50_ms']:.1f} ms p95={result['p95_ms']:.1f} ms "
              f"cuadros/s totales={result['frames_per_second']:.1f}", flush=True)
    report = dict(schema_version=3, measured_at=datetime.now(timezone.utc).isoformat(),
        scope="predict(CroppedFace) one session; full live frame with 1, 2 and 4 concurrent sessions",
        input=input_description,
        frame_input=(f"synthetic BGR {FRAME_SIZE[0]}x{FRAME_SIZE[1]} JPEG q{JPEG_QUALITY} in memory, one seed per session: "
                     "decode + YuNet + crop + classify; central crop if no face is detected; not saved"),
        model=dict(id=classifier.model.id, version=classifier.model.version,
                   sha256=digest, size_bytes=path.stat().st_size),
        environment=dict(os=platform.system(), os_version=platform.release(),
            architecture=platform.machine(), cpu=platform.processor(),
            logical_cpus=psutil.cpu_count(), physical_cpus=psutil.cpu_count(logical=False),
            total_ram_mib=psutil.virtual_memory().total / 1024**2,
            python=platform.python_version(), numpy=np.__version__,
            **runtime_metadata(classifier, args.model)),
        protocol=dict(runs=args.runs, samples_min=args.samples, warmup_per_run=args.warmup,
            min_seconds=args.min_seconds, max_seconds=args.max_seconds, rss_interval_ms=50,
            concurrent_sessions=list(CONCURRENT_SESSIONS), frame_samples_per_session=args.frame_samples,
            onnx_threads_per_session=args.threads),
        load=dict(seconds=load_seconds, rss_before_mib=baseline_rss,
            rss_after_mib=loaded_rss, rss_delta_mib=loaded_rss - baseline_rss),
        definitions=dict(fps="completed predictions / measured wall seconds; not browser FPS",
            cpu_process_percent="process user+system CPU / wall time *100; can exceed 100",
            cpu_percent="process CPU divided by logical CPUs; not total host utilization",
            ram="sampled whole-process RSS in MiB; includes imports/runtime; not exact model allocation",
            thread_zero="ONNX Runtime default, not zero worker threads",
            timeout="checked between predictions; cannot interrupt a hung prediction",
            concurrent_frame="full live frame latency over all sessions running at once; informative only"),
        results=results, concurrent_frame=concurrent)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Informe: {args.output}")
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
