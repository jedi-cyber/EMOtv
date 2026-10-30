"""Pasos de práctica en la sesión guiada: nivel en vivo, sostén, logro, tiempo
vencido, saltar y detener (SQLite en memoria, reloj falso y analizador falso;
sin modelos ni imágenes de personas)."""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from emotv.application.practice_tracker import PracticeTracker
from emotv.domain.guided_session import FrameAssessment, PracticeOutcome, QualityIssue
from emotv.domain.protocol import Protocol, ProtocolStep
from tests.integration.test_guided_sessions import frame, guided, post, state, stimuli, view, wait
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401

NEUTRAL = FrameAssessment((), "neutral", 0.9, {"neutral": 0.9, "happiness": 0.05, "surprise": 0.05})
HAPPY = FrameAssessment((), "happiness", 0.95, {"happiness": 0.95, "neutral": 0.05})
SLIGHT = FrameAssessment((), "neutral", 0.8, {"neutral": 0.8, "happiness": 0.15, "surprise": 0.05})
DARK = FrameAssessment((QualityIssue.TOO_DARK,), "happiness", 0.95, {"happiness": 0.95, "neutral": 0.05})
NO_FACE = FrameAssessment((QualityIssue.NO_FACE,))


def practice_protocol(env, *steps, for_children=False):  # noqa: F811
    """Protocolo guardado directamente: la API de protocolos aún no crea prácticas."""
    item = Protocol(id=str(uuid4()), family_id=str(uuid4()), version=1, owner_user_id=env.user_1.id,
                    name="Práctica", description="", for_children=for_children, created_at=env.clock.now,
                    steps=steps or (ProtocolStep.practice("happiness", 2, 20),))
    env.protocols.repository.add(item)
    return {"id": item.id, "for_children": for_children}


def start(env, *steps, calibrated=True):  # noqa: F811
    """Sesión en el primer ejercicio, con la base neutral de la calibración."""
    session_id, token = guided(env, practice_protocol(env, *steps))
    env.frame_result = NEUTRAL
    assert post(env, session_id, "calibration").status_code == 200
    for _ in range(5):
        frame(env, token)
        wait(env, 0.6)
    wait(env, 0.5)
    frame(env, token)                            # este cuadro cierra la calibración y empieza el ejercicio
    current = state(env, session_id)
    assert current["phase"] == "stimuli" and current["step_index"] == 0
    if not calibrated:
        env.guided._live.pop(session_id, None)  # como tras un reinicio: la base se perdió
    return session_id, token


def send(env, token, result, count=1, every=0.5):  # noqa: F811
    env.frame_result = result
    for _ in range(count):
        wait(env, every)
        frame(env, token)


def results(env, session_id):  # noqa: F811
    return env.guided.repository.list_practice_results(session_id)


def test_sostener_la_expresion_pedida_la_logra_y_avanza_tras_la_pausa(env):  # noqa: F811
    session_id, token = start(env)
    shown = view(env, token).json()
    # Sin ilustración no hay imagen; la cámara sigue enviando cuadros.
    assert shown["stimulus"] is None and shown["capture_frames"] is True
    assert env.client.get(f"/participant-view/{token}/stimulus").status_code == 404
    send(env, token, HAPPY, count=6)            # el nivel cruza el umbral al 1.0 s y se sostiene 2 s
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.ACHIEVED and item.seconds_to_achieve == 3.0
    assert item.relative_to_calibration is True and item.feedback_visible is True
    assert item.target_expression == "happiness" and 0.6 <= item.peak_level <= 1.0
    assert (item.analyzed_frames, item.flagged_frames) == (6, 0)
    assert item.emotion_model_id == "hsemotion_enet_b0_8_best_afew"
    # Pausa del logro: el paso sigue y ya no se analizan cuadros.
    assessed = env.frames_assessed
    send(env, token, HAPPY, count=2, every=0.5)
    assert env.frames_assessed == assessed and state(env, session_id)["phase"] == "stimuli"
    wait(env, 1.1)
    assert state(env, session_id)["phase"] == "finished"
    assert state(env, session_id)["captures"] == []   # la práctica no crea capturas
    assert [entry["step_index"] for entry in state(env, session_id)["steps_log"]] == [0]


def test_al_vencer_el_tiempo_se_registra_no_logrado_y_avanza(env):  # noqa: F811
    second = ProtocolStep.practice("surprise", 2, 10)
    session_id, token = start(env, ProtocolStep.practice("happiness", 2, 6), second)
    send(env, token, SLIGHT, count=8)           # la alegría apenas sube: nunca alcanza el umbral
    wait(env, 2.5)
    current = state(env, session_id)
    assert current["phase"] == "stimuli" and current["step_index"] == 1
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.TIMED_OUT and item.seconds_to_achieve is None
    assert item.peak_level < 0.6 and item.analyzed_frames == 8
    assert item.ended_at - item.started_at == timedelta(seconds=6)
    # Sin cuadros, el reloj del servidor también cierra el ejercicio.
    wait(env, 10)
    assert state(env, session_id)["phase"] == "finished"
    second_result = results(env, session_id)[1]
    assert second_result.outcome is PracticeOutcome.TIMED_OUT and second_result.analyzed_frames == 0


def test_un_cuadro_malo_no_sube_el_nivel_y_reinicia_el_sosten(env):  # noqa: F811
    session_id, token = start(env)
    send(env, token, HAPPY, count=3)            # 1.5 s: umbral alcanzado al 1.0 s
    tracker = env.guided._live[session_id].practice
    level = tracker.level
    send(env, token, DARK)                       # 2.0 s: problema de calidad
    assert tracker.level == level and tracker.above_since is None
    send(env, token, NO_FACE)                    # 2.5 s: sin rostro
    send(env, token, HAPPY, count=4)             # el sostén vuelve a empezar al 3.0 s
    assert results(env, session_id) == ()
    send(env, token, HAPPY)
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.ACHIEVED and item.seconds_to_achieve == 5.0
    assert (item.analyzed_frames, item.flagged_frames) == (8, 2)


def test_con_calibracion_el_nivel_es_relativo_a_la_base(env):  # noqa: F811
    session_id, token = start(env, ProtocolStep.practice("surprise", 2, 20))
    # Sorpresa 0.30 con base 0.05: (0.30 - 0.05) / 0.95 ≈ 0.26, por debajo del umbral.
    send(env, token, FrameAssessment((), "neutral", 0.7, {"neutral": 0.7, "surprise": 0.30}), count=10)
    tracker = env.guided._live[session_id].practice
    assert tracker.relative is True and 0.25 <= tracker.level <= 0.27


def test_sin_calibracion_el_nivel_usa_la_probabilidad_directa(env):  # noqa: F811
    session_id, token = start(env, ProtocolStep.practice("surprise", 2, 20), calibrated=False)
    send(env, token, FrameAssessment((), "neutral", 0.7, {"neutral": 0.7, "surprise": 0.30}), count=10)
    tracker = env.guided._live[session_id].practice
    assert tracker.relative is False and 0.29 <= tracker.level <= 0.30
    send(env, token, FrameAssessment((), "surprise", 0.9, {"surprise": 0.9, "neutral": 0.1}), count=8)
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.ACHIEVED and item.relative_to_calibration is False


def test_pedir_neutral_usa_la_probabilidad_directa_aunque_haya_calibracion(env):  # noqa: F811
    session_id, token = start(env, ProtocolStep.practice("neutral", 1, 20))
    send(env, token, NEUTRAL, count=5)
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.ACHIEVED and item.relative_to_calibration is False


def test_detener_a_mitad_del_ejercicio(env):  # noqa: F811
    session_id, token = start(env)
    send(env, token, HAPPY, count=2)
    assert post(env, session_id, "stop", {"reason": "participant"}).json()["phase"] == "stopped"
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.STOPPED and item.seconds_to_achieve is None
    assert item.analyzed_frames == 2
    assert session_id not in env.guided._live


def test_pedir_parar_con_un_marcador_tambien_detiene(env):  # noqa: F811
    session_id, token = start(env)
    marker = post(env, session_id, "markers", {"kind": "distracted"})
    assert marker.status_code == 201
    assert state(env, session_id)["markers"][0]["step_index"] == 0
    post(env, session_id, "markers", {"kind": "asked_to_stop"})
    assert state(env, session_id)["phase"] == "stopped"
    assert results(env, session_id)[0].outcome is PracticeOutcome.STOPPED


def test_saltar_un_ejercicio(env):  # noqa: F811
    session_id, token = start(env, ProtocolStep.practice("happiness", 2, 20), ProtocolStep.practice("sadness", 2, 20))
    send(env, token, HAPPY)
    assert post(env, session_id, "skip").status_code == 200
    assert state(env, session_id)["step_index"] == 1
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.SKIPPED and item.step_index == 0
    assert state(env, session_id)["steps_log"][0]["skipped"] is True


def test_detener_despues_de_lograrlo_no_cambia_el_resultado(env):  # noqa: F811
    session_id, token = start(env)
    send(env, token, HAPPY, count=6)
    post(env, session_id, "stop", {"reason": "conductor"})
    [item] = results(env, session_id)
    assert item.outcome is PracticeOutcome.ACHIEVED


def test_una_ilustracion_se_muestra_y_no_cuenta_como_estimulo(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = start(env, ProtocolStep.practice("happiness", 2, 20, illustration_id=emotional["id"]))
    assert view(env, token).json()["stimulus"] is not None
    assert env.client.get(f"/participant-view/{token}/stimulus").status_code == 200
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    assert metrics["emotional"] == [] and metrics["totals"]["emotional_stimuli"] == 0


def test_si_ya_se_analiza_un_cuadro_de_la_sesion_el_siguiente_se_descarta(env):  # noqa: F811
    session_id, token = start(env)
    live = env.guided._live[session_id]
    live.analyzing = True
    assessed = env.frames_assessed
    send(env, token, HAPPY, count=3)
    assert env.frames_assessed == assessed and live.practice is None
    live.analyzing = False
    send(env, token, HAPPY)
    assert env.frames_assessed == assessed + 1


def test_solo_los_cuadros_de_un_ejercicio_en_curso_se_descartan_sin_cupo(env):  # noqa: F811
    session_id, token = guided(env, practice_protocol(env))
    assert env.guided.practice_frame_drops_when_busy(token) is False      # calibración: espera su cupo
    session_id, token = start(env)
    assert env.guided.practice_frame_drops_when_busy(token) is True
    send(env, token, HAPPY, count=6)
    assert env.guided.practice_frame_drops_when_busy(token) is False      # logrado: pausa
    assert env.guided.practice_frame_drops_when_busy("otro") is False


def test_el_estado_en_memoria_no_crece_con_los_cuadros(env):  # noqa: F811
    session_id, token = start(env, ProtocolStep.practice("happiness", 2, 60))
    send(env, token, SLIGHT, count=5, every=0.05)
    tracker = env.guided._live[session_id].practice
    assert not hasattr(tracker, "__dict__")      # solo acumuladores fijos (__slots__)
    snapshot = {name: type(getattr(tracker, name)) for name in PracticeTracker.__slots__}
    send(env, token, SLIGHT, count=400, every=0.05)
    assert env.guided._live[session_id].practice is tracker and tracker.analyzed == 405
    assert {name: type(getattr(tracker, name)) for name in PracticeTracker.__slots__} == snapshot
    assert len(env.guided._live) == 1
    assert state(env, session_id)["captures"] == [] and results(env, session_id) == ()


def test_la_pantalla_de_la_persona_no_recibe_resultados(env):  # noqa: F811
    session_id, token = start(env)
    send(env, token, HAPPY, count=6)
    shown = view(env, token).json()
    text = str(shown).lower()
    assert not any(word in text for word in ("happiness", "level", "probab", "confidence", "quality"))
    assert frame(env, token).json() == {"received": True}
