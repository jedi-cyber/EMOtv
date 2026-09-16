import hashlib
import json
from types import SimpleNamespace
import sys

import numpy as np
import pytest

from emotv.application import EmotionModelCatalog
from emotv.domain import CroppedFace
from emotv.infrastructure.vision.emotion_classifier.hardlyhumans_classifier import HardlyHumansEmotionClassifier, canonical_labels
from emotv.infrastructure.vision.emotion_classifier.emotion_frame_analyzer import EmotionFrameAnalyzer
from scripts.emotion.download_hardlyhumans_model import download_model, REVISION


LABELS = dict(enumerate(["anger", "contempt", "sad", "happy", "neutral", "disgust", "fear", "surprise"]))


def test_canonical_labels_preserve_output_order():
    assert canonical_labels(LABELS) == ("anger", "contempt", "sadness", "happiness", "neutral", "disgust", "fear", "surprise")
    with pytest.raises(ValueError): canonical_labels({0: "LABEL_0"})


def test_default_unchanged_and_vit_optional(tmp_path):
    assert EmotionModelCatalog().default.id == "ferplus_onnx"
    assert not EmotionModelCatalog().get("hardlyhumans_vit").is_default
    with pytest.raises(FileNotFoundError): HardlyHumansEmotionClassifier(tmp_path)


def test_vit_rejects_grayscale_and_double_normalized_inputs():
    classifier = HardlyHumansEmotionClassifier.__new__(HardlyHumansEmotionClassifier)
    for image in (np.zeros((64, 64), np.uint8), np.zeros((64, 64, 3), np.float32)):
        with pytest.raises(ValueError): classifier.predict(CroppedFace(image, (0, 0, 64, 64), 1))


def test_predict_converts_rgb_and_maps_softmax():
    torch = pytest.importorskip("torch")
    classifier = HardlyHumansEmotionClassifier.__new__(HardlyHumansEmotionClassifier)
    classifier._torch = torch
    classifier.labels = canonical_labels(LABELS)
    def processor(images, return_tensors):
        assert images[0, 0].tolist() == [30, 20, 10]
        assert return_tensors == "pt"
        return {"pixel_values": torch.zeros((1, 3, 224, 224))}
    classifier.processor = processor
    classifier.network = lambda **kwargs: SimpleNamespace(logits=torch.tensor([[0., 0., 0., 5., 0., 0., 0., 0.]]))
    image = np.full((2, 2, 3), [10, 20, 30], np.uint8)
    emotion, confidence = classifier.predict(CroppedFace(image, (0, 0, 2, 2), 1))
    assert emotion == "happiness"
    assert 0 <= confidence <= 1


def test_frame_analyzer_keeps_color_and_original_crop():
    classifier = HardlyHumansEmotionClassifier.__new__(HardlyHumansEmotionClassifier)
    analyzer = EmotionFrameAnalyzer(detector=SimpleNamespace(), classifier=classifier)
    assert analyzer.preprocessor.target_size is None
    assert not analyzer.preprocessor.grayscale
    frame = np.full((40, 40, 3), 123, np.uint8)
    detection = SimpleNamespace(bbox=(10, 10, 10, 10), confidence=1)
    face = analyzer.preprocessor.process(frame, detection)
    assert face.image.shape == (14, 14, 3)
    assert face.image.dtype == np.uint8


@pytest.mark.parametrize("corrupt", [False, True])
def test_snapshot_checksum_and_no_overwrite(tmp_path, monkeypatch, corrupt):
    payload = b"test-weights"
    sibling = SimpleNamespace(rfilename="model.safetensors", lfs=SimpleNamespace(sha256=hashlib.sha256(payload).hexdigest(), size=len(payload)))
    def snapshot(repo_id, revision, allow_patterns, local_dir, max_workers):
        assert revision == REVISION
        assert max_workers == 1
        local_dir.mkdir(exist_ok=True)
        (local_dir / "config.json").write_text(json.dumps(dict(model_type="vit", id2label=LABELS)))
        (local_dir / "preprocessor_config.json").write_text("{}")
        (local_dir / "README.md").write_text("- **License:** MIT")
        (local_dir / "model.safetensors").write_bytes(b"corrupt" if corrupt else payload)
    api = SimpleNamespace(model_info=lambda *a, **kw: SimpleNamespace(sha=REVISION, siblings=[sibling]))
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=lambda: api, snapshot_download=snapshot))
    target = tmp_path / "model"
    if corrupt:
        with pytest.raises(ValueError, match="Checksum"): download_model(target)
        assert not target.exists()
    else:
        assert download_model(target) == target
        assert (target / "emotv-source.json").is_file()
        with pytest.raises(FileExistsError): download_model(target)
