from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace

import pytest

from emotv.application.model_admission import AdmissionLimits, evaluate_resources
from emotv.infrastructure.vision.emotion_classifier import model_admission as module


@pytest.mark.parametrize("latency,ram,cpu,state", [
    (40, 4096, 20, "SUPPORTED"), (250, 4096, 20, "WARNING"),
    (1000, 4096, 20, "BLOCKED"), (40, 100, 20, "BLOCKED"),
    (40, 900, 20, "WARNING"), (40, 4096, 75, "WARNING"),
    (40, 4096, 95, "BLOCKED"), (float("nan"), 4096, 20, "BLOCKED"),
])
def test_policy_boundaries(latency, ram, cpu, state):
    result = evaluate_resources(p95_ms=latency, peak_ram_mib=200,
                                available_ram_mib=ram, cpu_percent=cpu,
                                limits=AdmissionLimits())
    assert result["state"] == state


def test_invalid_limits_fail():
    with pytest.raises(ValueError): AdmissionLimits(warn_latency_ms=1000)
    with pytest.raises(ValueError): AdmissionLimits(ram_safety_factor=.5)


@pytest.fixture
def evaluator(tmp_path, monkeypatch):
    weights = tmp_path / "weights"
    weights.write_bytes(b"verified")
    report = dict(model=dict(id="ferplus_onnx", version="1.0",
                            sha256=hashlib.sha256(b"verified").hexdigest(), size_bytes=8),
                  measured_at=datetime.now(timezone.utc).isoformat(),
                  environment=dict(os=module.platform.system(), architecture=module.platform.machine(),
                                   cpu=module.platform.processor(), logical_cpus=module.psutil.cpu_count(),
                                   python=module.platform.python_version(), onnxruntime="test"),
                  results=[dict(samples=100, elapsed_seconds=3, target_reached=True,
                                p95_ms=40, ram_peak_mib=200) for _ in range(3)])
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    service = module.ServerModelAdmission({})
    service.paths["ferplus_onnx"] = weights, path
    monkeypatch.setattr(module, "version", lambda package: "test")
    monkeypatch.setattr(module.psutil, "cpu_percent", lambda interval: 20)
    monkeypatch.setattr(module.psutil, "virtual_memory", lambda: SimpleNamespace(available=4096 * 1024**2))
    return service, path, report


def test_valid_report_and_live_resources(evaluator):
    service, _, _ = evaluator
    assert service.evaluate("ferplus_onnx")["state"] == "SUPPORTED"
    assert service.evaluate("not-allowed")["state"] == "BLOCKED"


@pytest.mark.parametrize("reason", ["missing", "invalid", "stale", "future", "hash", "environment", "runtime", "samples", "nan"])
def test_untrusted_reports_fail_closed(evaluator, reason):
    service, path, report = evaluator
    if reason == "missing": path.unlink()
    elif reason == "invalid": path.write_text("invalid")
    else:
        if reason == "stale": report["measured_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        if reason == "future": report["measured_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        if reason == "hash": report["model"]["sha256"] = "wrong"
        if reason == "environment": report["environment"]["cpu"] = "different"
        if reason == "runtime": report["environment"]["onnxruntime"] = "different"
        if reason == "samples": report["results"][0]["samples"] = 3
        if reason == "nan": report["results"][0]["ram_peak_mib"] = float("nan")
        path.write_text(json.dumps(report), encoding="utf-8")
    assert service.evaluate("ferplus_onnx")["state"] == "BLOCKED"


def test_dynamic_cpu_block_and_recovery(evaluator, monkeypatch):
    service, _, _ = evaluator
    monkeypatch.setattr(module.psutil, "cpu_percent", lambda interval: 99)
    assert service.evaluate("ferplus_onnx")["state"] == "BLOCKED"
    monkeypatch.setattr(module.psutil, "cpu_percent", lambda interval: 10)
    assert service.evaluate("ferplus_onnx")["state"] == "SUPPORTED"
