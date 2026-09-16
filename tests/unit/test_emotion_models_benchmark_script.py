import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.emotion import run_emotion_models_benchmark as script


@pytest.mark.parametrize("model_id,shape", [
    ("ferplus_onnx", (64, 64)),
    ("hardlyhumans_vit", (224, 224, 3)),
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


@pytest.mark.parametrize("model_id", ["ferplus_onnx", "hardlyhumans_vit"])
def test_report_uses_selected_model_and_backend(tmp_path, monkeypatch, model_id):
    weights = tmp_path / "weights"
    weights.write_bytes(b"weights")
    monkeypatch.setitem(script.MODEL_WEIGHTS, model_id, weights)
    options = SimpleNamespace(intra_op_num_threads=0, inter_op_num_threads=0)
    classifier = SimpleNamespace(
        model=SimpleNamespace(id=model_id, version="test", emotion_labels=("neutral",)),
        predict=lambda face: ("neutral", .5),
        session=SimpleNamespace(get_session_options=lambda: options,
                                get_providers=lambda: ["CPUExecutionProvider"]),
        _torch=SimpleNamespace(__version__="test", get_num_threads=lambda: 4,
                               get_num_interop_threads=lambda: 2))
    selected = []
    def factory(identifier):
        selected.append(identifier)
        return classifier
    monkeypatch.setattr(script, "create_emotion_classifier", factory)
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(__version__="test"))
    def benchmark(predict, **kwargs):
        predict()
        return dict(inference_time_ms=10, p95_ms=12, fps=100,
                    cpu_percent=20, ram_peak_mib=200)
    monkeypatch.setattr(script, "benchmark_predict", benchmark)
    output = tmp_path / "report.json"
    assert script.main(["--model", model_id, "--runs", "1", "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert selected == [model_id]
    assert report["model"]["id"] == model_id
    assert report["model"]["size_bytes"] == 7
    assert report["environment"]["backend"] == ("pytorch" if model_id == "hardlyhumans_vit" else "onnxruntime")
    with pytest.raises(SystemExit):
        script.main(["--model", model_id, "--output", str(output)])
    assert selected == [model_id]  # Refuses overwrite before loading.


def test_missing_weights_fail_before_loading(tmp_path, monkeypatch):
    monkeypatch.setitem(script.MODEL_WEIGHTS, "hardlyhumans_vit", tmp_path / "missing")
    with pytest.raises(SystemExit):
        script.main(["--model", "hardlyhumans_vit"])
