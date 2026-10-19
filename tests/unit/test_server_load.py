"""Configuración de carga, hilos de onnxruntime y benchmark concurrente (sin pesos ni red)."""
import threading
import time

import pytest

from emotv.config import ServerLoadSettings, get_server_load_settings
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import session_options
from emotv.infrastructure.vision.emotion_classifier.model_admission import concurrent_frame_p95
from emotv.shared.performance.model_benchmark import benchmark_concurrent


def test_defaults_leave_one_core_free(monkeypatch):
    import emotv.config as config

    monkeypatch.setattr(config.os, "sched_getaffinity", lambda pid: set(range(4)), raising=False)
    assert ServerLoadSettings().max_concurrent_analyses == 3
    monkeypatch.setattr(config.os, "sched_getaffinity", lambda pid: {0}, raising=False)
    assert ServerLoadSettings().max_concurrent_analyses == 1  # mínimo 1


def test_load_settings_from_environment():
    settings = get_server_load_settings({
        "MAX_CONCURRENT_ANALYSES": "2", "MAX_ACTIVE_SESSIONS": "6", "ANALYSIS_BUSY_WAIT_SECONDS": "3",
        "LIVE_IDLE_TIMEOUT_SECONDS": "45", "ONNX_THREADS_PER_SESSION": "2",
    })
    assert (settings.max_concurrent_analyses, settings.max_active_sessions, settings.busy_wait_seconds,
            settings.idle_timeout_seconds, settings.onnx_threads_per_session) == (2, 6, 3.0, 45.0, 2)
    assert get_server_load_settings({"MAX_CONCURRENT_ANALYSES": ""}).max_concurrent_analyses >= 1
    for name, value in (("MAX_CONCURRENT_ANALYSES", "0"), ("MAX_ACTIVE_SESSIONS", "x"),
                        ("LIVE_IDLE_TIMEOUT_SECONDS", "1"), ("ONNX_THREADS_PER_SESSION", "1.5")):
        with pytest.raises(ValueError, match=name):
            get_server_load_settings({name: value})


def test_onnx_session_threads_are_limited_per_session():
    assert session_options(None) is None  # sin límite: valor por defecto de ONNX Runtime
    options = session_options(2)
    assert (options.intra_op_num_threads, options.inter_op_num_threads) == (2, 1)
    for value in (0, True):
        with pytest.raises(ValueError):
            session_options(value)


def test_concurrent_benchmark_runs_sessions_at_the_same_time():
    running, peak, lock = [0], [0], threading.Lock()

    def step():
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        time.sleep(0.005)
        with lock:
            running[0] -= 1

    result = benchmark_concurrent([step, step, step, step], warmup=1, samples_per_session=10)
    assert result["sessions"] == 4 and result["samples"] == 40 and result["target_reached"]
    assert peak[0] > 1  # hubo cuadros de varias sesiones a la vez
    assert 0 < result["p50_ms"] <= result["p95_ms"] <= result["max_ms"]


def test_concurrent_benchmark_reports_a_failing_session():
    def broken():
        raise ValueError("salida inválida")

    with pytest.raises(RuntimeError, match="sesión"):
        benchmark_concurrent([broken, lambda: None], warmup=0, samples_per_session=2)
    with pytest.raises(ValueError):
        benchmark_concurrent([], samples_per_session=2)


@pytest.mark.parametrize("report,expected", [
    ({"concurrent_frame": {"1": {"p95_ms": 90}, "2": {"p95_ms": 150.5}, "4": {"p95_ms": 300}}},
     {"1": 90.0, "2": 150.5, "4": 300.0}),
    ({}, None),                                          # informe anterior
    ({"concurrent_frame": {"1": {"p95_ms": float("nan")}}}, None),
    ({"concurrent_frame": {"uno": {"p95_ms": 90}}}, None),
    ({"concurrent_frame": "x"}, None),
])
def test_concurrent_measurement_is_informative_and_never_blocks(report, expected):
    assert concurrent_frame_p95(report) == expected
