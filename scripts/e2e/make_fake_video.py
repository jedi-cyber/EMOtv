"""Genera el video .y4m que Chromium usa como cámara simulada en las pruebas e2e.

Uso (desde la raíz del repositorio):
    python scripts/e2e/make_fake_video.py
    python scripts/e2e/make_fake_video.py --empty-only

El video tiene dos tramos y Chromium lo repite en bucle:

1. Rostro: cada imagen de ``web/e2e/fixtures/faces/`` se muestra fija durante
   ``--seconds-per-image`` segundos. Sirve para que el analizador registre una
   expresión estable.
2. Sin persona: un fondo neutro con ruido leve durante ``--empty-seconds``.
   Sirve para comprobar que la actividad no avanza si nadie está frente a la
   cámara.

Las imágenes las aporta quien ejecuta las pruebas y nunca se suben al
repositorio (ver ``web/e2e/fixtures/README.md``). Sin imágenes, o con
``--empty-only``, se genera solo el tramo sin persona y las pruebas que
necesitan un rostro se saltan.

Además del video escribe ``camera.json`` con la duración de cada tramo; las
pruebas lo leen para saber si hay rostro y cuánto dura.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "web" / "e2e" / "fixtures" / "faces"
DEFAULT_OUTPUT = ROOT / "web" / "e2e" / "fixtures" / "generated" / "camera.y4m"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def load_dependencies():
    try:
        import cv2
        import numpy as np
    except ImportError as error:  # pragma: no cover - mensaje para quien ejecuta el script
        raise SystemExit(
            "Faltan opencv-python y numpy. Instala el proyecto con: python -m pip install -e \".[dev]\""
        ) from error
    return cv2, np


def find_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)


def fit_image(cv2, np, image, width: int, height: int):
    """Encaja la imagen sin deformarla sobre un fondo gris neutro."""
    canvas = np.full((height, width, 3), 96, dtype=np.uint8)
    scale = min(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(image, (max(1, int(image.shape[1] * scale)), max(1, int(image.shape[0] * scale))),
                         interpolation=cv2.INTER_AREA)
    top = (height - resized.shape[0]) // 2
    left = (width - resized.shape[1]) // 2
    canvas[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
    return canvas


def empty_frame(np, rng, width: int, height: int):
    """Fondo de pared con un degradado y ruido leve: no hay ninguna persona."""
    gradient = np.linspace(110, 150, height, dtype=np.float32)[:, None]
    base = np.repeat(gradient, width, axis=1)
    noise = rng.normal(0, 3, (height, width)).astype(np.float32)
    gray = np.clip(base + noise, 0, 255).astype(np.uint8)
    return np.dstack([gray, gray, gray])


def write_frame(cv2, stream, frame_bgr) -> None:
    stream.write(b"FRAME\n")
    stream.write(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YUV_I420).tobytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Carpeta con imágenes de rostro")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Ruta del video .y4m")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--seconds-per-image", type=float, default=12.0)
    parser.add_argument("--empty-seconds", type=float, default=45.0)
    parser.add_argument("--empty-only", action="store_true", help="Genera solo el tramo sin persona")
    args = parser.parse_args(argv)

    if args.width % 2 or args.height % 2:
        parser.error("El ancho y el alto deben ser pares (formato 4:2:0)")
    if args.fps < 1 or args.seconds_per_image <= 0 or args.empty_seconds <= 0:
        parser.error("fps y duraciones deben ser positivos")

    cv2, np = load_dependencies()
    images = [] if args.empty_only else find_images(args.input)
    faces = []
    for path in images:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"Se omite {path.name}: no se pudo leer como imagen", file=sys.stderr)
            continue
        faces.append(fit_image(cv2, np, image, args.width, args.height))
    if not faces and not args.empty_only:
        print(f"No hay imágenes en {args.input}; se genera solo el tramo sin persona.", file=sys.stderr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    face_frames = int(round(args.seconds_per_image * args.fps))
    empty_frames = int(round(args.empty_seconds * args.fps))
    rng = np.random.default_rng(7)
    with args.output.open("wb") as stream:
        stream.write(f"YUV4MPEG2 W{args.width} H{args.height} F{args.fps}:1 Ip A1:1 C420jpeg\n".encode("ascii"))
        for face in faces:
            for _ in range(face_frames):
                write_frame(cv2, stream, face)
        for _ in range(empty_frames):
            write_frame(cv2, stream, empty_frame(np, rng, args.width, args.height))

    face_seconds = len(faces) * face_frames / args.fps
    metadata = {
        "has_face": bool(faces),
        "face_seconds": face_seconds,
        "empty_seconds": empty_frames / args.fps,
        "fps": args.fps,
        "width": args.width,
        "height": args.height,
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Video generado: {args.output} ({face_seconds:g} s con rostro, {metadata['empty_seconds']:g} s sin persona)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
