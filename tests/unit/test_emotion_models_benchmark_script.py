import json
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from scripts.emotion import run_emotion_models_benchmark as script


@pytest.mark.parametrize("model_id,shape", [
    ("ferplus_onnx", (64, 64)),
    ("hardlyhumans_vit", (224, 224, 3)),
    ("hsemotion_enet_b0_8_best_afew", (224, 224, 3)),
])
def test_native_inputs_are_deterministic(model_id, shape):
    faces, description = script.benchmark_faces(model_id)
    assert len(faces) == 16
    assert faces[0].image.shape == shape
    assert faces[0].image.dtype == np.uint8
    assert np.array_equal(faces[0].image, script.benchmark_faces(model_id)[0][0].image)
    assert "not accuracy" in description


def test_unintegrated_model_is_rejected():
    with pytest.raises(ValueError, match="no integrado"):
        script.benchmark_faces("enet_b2_8")
    with pytest.raises(SystemExit):
        script.main(["--model", "enet_b2_8"])


class FakeDetector:
    """Detector falso: devuelve las detecciones dadas y registra cada cuadro recibido."""

    def __init__(self, detections=()):
        self.detections, self.frames = list(detections), []

    def detect(self, frame):
        self.frames.append(frame.shape)
        return self.detections


def _classifier(model_id, seen=None):
    options = SimpleNamespace(intra_op_num_threads=0, inter_op_num_threads=0)

    def predict(face):
        if seen is not None:
            seen.append(face.image.shape)
        return "neutral", .5

    return SimpleNamespace(
        model=SimpleNamespace(id=model_id, version="test", emotion_labels=("neutral",)),
        predict=predict,
        face_preprocessor_options=dict(padding_ratio=0.0, target_size=None, grayscale=False, normalize=False),
        session=SimpleNamespace(get_session_options=lambda: options,
                                get_providers=lambda: ["CPUExecutionProvider"]),
        _torch=SimpleNamespace(__version__="test", get_num_threads=lambda: 4,
                               get_num_interop_threads=lambda: 2))


def test_synthetic_frame_is_a_640x480_jpeg_in_memory():
    jpeg = script.synthetic_frame_jpeg()
    assert jpeg[:2] == b"\xff\xd8"  # marcador SOI de JPEG
    frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert frame.shape == (480, 640, 3)
    assert jpeg == script.synthetic_frame_jpeg() != script.synthetic_frame_jpeg(seed=7)


@pytest.mark.parametrize("detections,crop_shape", [
    ((), (200, 200, 3)),  # sin rostro: caja central, así el recorte y la clasificación cuentan
    ((script.FaceDetection(100, 50, 120, 160, .9),), (160, 120, 3)),
])
def test_frame_step_decodes_detects_crops_and_classifies(detections, crop_shape):
    from emotv.infrastructure.vision.face_processing.face_preprocessor import FacePreprocessor

    seen = []
    classifier = _classifier("hsemotion_enet_b0_8_best_afew", seen)
    detector = FakeDetector(detections)
    step = script.frame_step(script.synthetic_frame_jpeg(), detector,
                             FacePreprocessor(**classifier.face_preprocessor_options), classifier)
    step()
    step()
    assert detector.frames == [(480, 640, 3)] * 2
    assert seen == [crop_shape] * 2


def test_frame_step_rejects_invalid_classifier_output():
    from emotv.infrastructure.vision.face_processing.face_preprocessor import FacePreprocessor

    classifier = _classifier("ferplus_onnx")
    classifier.predict = lambda face: ("joy", .5)
    step = script.frame_step(script.synthetic_frame_jpeg(), FakeDetector(),
                             FacePreprocessor(**classifier.face_preprocessor_options), classifier)
    with pytest.raises(ValueError, match="inválida"):
        step()


@pytest.mark.parametrize("model_id", ["ferplus_onnx", "hsemotion_enet_b0_8_best_afew", "hardlyhumans_vit"])
def test_report_uses_selected_model_and_backend(tmp_path, monkeypatch, model_id):
    weights = tmp_path / "weights"
    weights.write_bytes(b"weights")
    monkeypatch.setitem(script.MODEL_WEIGHTS, model_id, weights)
    selected, detectors = [], []

    def factory(identifier, **options):
        selected.append((identifier, options.get("intra_op_threads")))
        return _classifier(identifier)

    def detector():
        detectors.append(FakeDetector())
        return detectors[-1]

    monkeypatch.setattr(script, "create_emotion_classifier", factory)
    monkeypatch.setattr(script, "create_face_detector", detector)
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(__version__="test"))
    # Ninguna imagen se escribe en disco durante la medición.
    monkeypatch.setattr(cv2, "imwrite", lambda *args, **kwargs: pytest.fail("no debe guardar imágenes"))

    def benchmark(predict, **kwargs):
        predict()
        return dict(inference_time_ms=10, p95_ms=12, fps=100,
                    cpu_percent=20, ram_peak_mib=200)
    monkeypatch.setattr(script, "benchmark_predict", benchmark)
    output = tmp_path / "report.json"
    assert script.main(["--model", model_id, "--runs", "1", "--frame-samples", "3", "--warmup", "1",
                        "--threads", "2", "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    # Uno para predict y una sesión propia por cada sesión simultánea: 1 + 2 + 4.
    assert selected == [(model_id, None)] + [(model_id, 2)] * 7
    assert len(detectors) == 7 and all(item.frames for item in detectors)
    assert report["model"]["id"] == model_id
    assert report["model"]["size_bytes"] == 7
    assert report["environment"]["backend"] == ("pytorch" if model_id == "hardlyhumans_vit" else "onnxruntime")
    assert set(report["concurrent_frame"]) == {"1", "2", "4"}
    assert report["concurrent_frame"]["4"]["sessions"] == 4 and report["concurrent_frame"]["4"]["samples"] == 12
    assert report["protocol"]["onnx_threads_per_session"] == 2
    # Las únicas escrituras son los pesos de prueba y el informe.
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.json", "weights"]
    with pytest.raises(SystemExit):
        script.main(["--model", model_id, "--output", str(output)])
    assert len(selected) == 8  # Refuses overwrite before loading.


def test_invalid_thread_limit_is_rejected():
    with pytest.raises(SystemExit):
        script.main(["--model", "ferplus_onnx", "--threads", "0"])


def test_missing_weights_fail_before_loading(tmp_path, monkeypatch):
    monkeypatch.setitem(script.MODEL_WEIGHTS, "hardlyhumans_vit", tmp_path / "missing")
    with pytest.raises(SystemExit):
        script.main(["--model", "hardlyhumans_vit"])
