"""Nivel de la práctica, su configuración, el nivel relativo a la base neutral y
el cupo sin espera (sin modelos ni imágenes)."""
from __future__ import annotations

import asyncio
import threading

import pytest

from emotv.application.neutral_calibration import NeutralCalibration
from emotv.application.practice_tracker import PracticeTracker
from emotv.config import PracticeSettings, ServerLoadSettings, get_practice_settings
from emotv.interfaces.web.analysis_capacity import AnalysisCapacity


def tracker(**fields):
    base = dict(threshold=0.6, release_threshold=0.55, smoothing_seconds=0.8)
    return PracticeTracker(0, 0.0, 2.0, False, **{**base, **fields})


# --- Seguidor ---------------------------------------------------------------------------

def test_el_nivel_sube_de_forma_suave_y_guarda_el_maximo():
    item = tracker()
    levels = []
    for second in (0.5, 1.0, 1.5):
        item.add(second, 1.0)
        levels.append(item.level)
    assert levels == sorted(levels) and 0.4 < levels[0] < 0.5 and item.peak == levels[-1]
    item.add(2.0, 0.0)
    assert item.level < levels[-1] and item.peak == levels[-1]


def test_se_logra_al_sostener_el_umbral():
    item = tracker(smoothing_seconds=0.0)       # sin suavizado: el nivel es el último valor
    assert not item.add(0.5, 0.7) and item.above_since == 0.5
    assert not item.add(1.5, 0.7)
    assert item.add(2.5, 0.7)


def test_histeresis_entre_los_dos_umbrales():
    item = tracker(smoothing_seconds=0.0)
    item.add(0.5, 0.7)
    item.add(1.0, 0.57)                          # entre 0.55 y 0.6: el sostén sigue
    assert item.above_since == 0.5
    item.add(1.5, 0.5)                           # bajo 0.55: se pierde
    assert item.above_since is None


def test_un_hueco_largo_entre_cuadros_pesa_como_dos_segundos():
    a, b = tracker(), tracker()
    a.add(2.0, 1.0)
    b.add(60.0, 1.0)
    assert a.level == pytest.approx(b.level)


def test_cuadro_sin_valor_cuenta_como_marcado():
    item = tracker(smoothing_seconds=0.0)
    item.add(0.5, 0.9)
    assert not item.add(1.0, None)
    assert (item.analyzed, item.flagged, item.level, item.above_since) == (1, 1, 0.9, None)


# --- Calibración --------------------------------------------------------------------------

def test_nivel_relativo_a_la_base_neutral():
    clock = [0.0]
    calibration = NeutralCalibration(seconds=1.0, min_samples=1, clock=lambda: clock[0])
    with pytest.raises(ValueError, match="Sin calibración"):
        calibration.relative_level({"happiness": 0.5}, "happiness")
    calibration.start()
    calibration.add({"happiness": 0.2, "neutral": 0.8})
    clock[0] = 1.0
    calibration.add({"happiness": 0.2, "neutral": 0.8})
    assert calibration.relative_level({"happiness": 0.6}, "happiness") == pytest.approx(0.5)
    assert calibration.relative_level({"happiness": 0.1}, "happiness") == 0.0
    assert calibration.relative_level({"happiness": 1.0}, "happiness") == 1.0
    assert calibration.relative_level({"surprise": 0.3}, "surprise") == pytest.approx(0.3)


# --- Configuración ------------------------------------------------------------------------

def test_valores_iniciales_del_documento():
    assert get_practice_settings({}) == PracticeSettings(0.6, 0.55, 0.8, 2.0)


def test_valores_desde_el_entorno():
    settings = get_practice_settings({"PRACTICE_THRESHOLD": "0.7", "PRACTICE_RELEASE_THRESHOLD": "0.6",
                                      "PRACTICE_SMOOTHING_SECONDS": "0", "PRACTICE_SUCCESS_PAUSE_SECONDS": "3"})
    assert settings == PracticeSettings(0.7, 0.6, 0.0, 3.0)


@pytest.mark.parametrize("name, value", [
    ("PRACTICE_THRESHOLD", "0"), ("PRACTICE_THRESHOLD", "1.5"), ("PRACTICE_RELEASE_THRESHOLD", "-0.1"),
    ("PRACTICE_SMOOTHING_SECONDS", "11"), ("PRACTICE_SUCCESS_PAUSE_SECONDS", "-1"),
    ("PRACTICE_THRESHOLD", "alto"),
])
def test_valores_fuera_de_rango(name, value):
    with pytest.raises(ValueError, match=name):
        get_practice_settings({name: value})


def test_el_umbral_de_salida_es_menor_que_el_de_entrada():
    with pytest.raises(ValueError, match="menor que PRACTICE_THRESHOLD"):
        get_practice_settings({"PRACTICE_THRESHOLD": "0.5", "PRACTICE_RELEASE_THRESHOLD": "0.5"})


# --- Cupo sin espera ----------------------------------------------------------------------

def test_sin_cupo_libre_el_cuadro_se_descarta_sin_esperar():
    async def scenario():
        capacity = AnalysisCapacity(ServerLoadSettings(max_concurrent_analyses=1, busy_wait_seconds=5.0))
        release = threading.Event()
        busy = asyncio.ensure_future(capacity.run(release.wait, 5))
        await asyncio.sleep(0.05)
        dropped = await asyncio.wait_for(capacity.try_run(lambda: "no"), timeout=1.0)
        release.set()
        await busy
        done = await capacity.try_run(lambda: "sí")
        return dropped, done

    assert asyncio.run(scenario()) == ((False, None), (True, "sí"))
