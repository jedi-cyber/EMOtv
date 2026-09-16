"""Prueba sin cámara de un adaptador; la entrada sintética no evalúa precisión."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import cv2
import numpy as np
from emotv.domain import CroppedFace
from emotv.infrastructure.vision.emotion_classifier import create_emotion_classifier


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="ferplus_onnx")
    parser.add_argument("--image", type=Path, help="Rostro ya recortado; se lee, no se guarda")
    args = parser.parse_args()
    classifier = create_emotion_classifier(args.model)
    if args.image:
        image = cv2.imread(str(args.image))
        if image is None:
            parser.error("No se pudo leer la imagen")
    else:
        print("Entrada sintética: solo prueba técnica, no precisión")
        image = np.random.default_rng(2026).integers(0, 256, (224, 224, 3), dtype=np.uint8)
    if args.model == "ferplus_onnx":
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    print(args.model, classifier.predict(CroppedFace(image, (0, 0, image.shape[1], image.shape[0]), 1)))


if __name__ == "__main__":
    main()
