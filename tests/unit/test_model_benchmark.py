import pytest
from emotv.shared.performance.model_benchmark import benchmark_predict, summarize


def test_summary_defines_cpu_and_throughput():
    result = summarize([10, 20, 30], .1, .2, 4, [100, 120])
    assert result["inference_time_ms"] == 20
    assert result["p50_ms"] == 20
    assert result["fps"] == 30
    assert result["cpu_process_percent"] == 200
    assert result["cpu_percent"] == 50
    assert result["ram_peak_mib"] == 120


def test_warmup_excluded():
    calls = []
    result = benchmark_predict(lambda: calls.append(1), warmup=2, samples=3, min_seconds=0)
    assert len(calls) == 5
    assert result["samples"] == 3
    assert result["target_reached"]


def test_errors_do_not_produce_successful_measurements():
    def fail(): raise RuntimeError("prediction failed")
    with pytest.raises(RuntimeError):
        benchmark_predict(fail, warmup=0)
    with pytest.raises(ValueError):
        benchmark_predict(lambda: None, samples=0)
