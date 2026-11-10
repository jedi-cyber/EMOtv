"""La cámara es complementaria: un protocolo solo de reconocimientos se aplica sin
calibración, sin modelo facial y sin analizar cuadros; uno con práctica facial
sigue calibrando como antes (SQLite en memoria, reloj falso y analizador falso;
sin modelos ni imágenes de personas)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from emotv.domain.guided_session import PracticeOutcome, RecognitionOutcome
from emotv.domain.protocol import Protocol, ProtocolKind, ProtocolStep
from tests.integration.test_guided_sessions import (
    calibrate,
    create_questionnaire,
    frame,
    guided,
    post,
    protocol,
    state,
    step,
    stimuli,
    view,
    wait,
)
from tests.integration.test_practice_sessions import HAPPY, NEUTRAL, practice_protocol, send
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_recognition_sessions import answer, recognition, sad_stimulus

T0 = datetime(2026, 11, 6, tzinfo=timezone.utc)


def no_model():
    raise RuntimeError("El modelo facial no está disponible en el servidor")


# --- Dominio ----------------------------------------------------------------------------


def _protocol(*steps, kind=ProtocolKind.PRACTICE):
    return Protocol(id="p", family_id="f", version=1, owner_user_id="u", name="P", description="",
                    for_children=False, created_at=T0, steps=steps, kind=kind)


def test_solo_los_reconocimientos_no_usan_la_camara():
    only = _protocol(ProtocolStep.recognition("s1", 10, target_expression="sadness"),
                     ProtocolStep.recognition("s2", 10, target_expression="happiness", situation="Ganó"))
    assert only.uses_camera is False
    assert _protocol(ProtocolStep.practice("happiness", 2, 20)).uses_camera is True
    assert _protocol(ProtocolStep.practice("happiness", 2, 20, illustration_id="s", imitate=True)).uses_camera is True
    assert _protocol(ProtocolStep("s", 6, 2)).uses_camera is True
    # Basta un paso con cámara para necesitarla.
    assert _protocol(ProtocolStep.recognition("s1", 10, target_expression="sadness"),
                     ProtocolStep.practice("happiness", 2, 20)).uses_camera is True
    # El examen simulado no tiene pasos y siempre usa la cámara.
    assert _protocol(kind=ProtocolKind.EXAM).uses_camera is True


# --- Protocolo solo de reconocimiento ---------------------------------------------------


def ready(env, *steps, **options):  # noqa: F811
    """Sesión sin cámara preparada: espera «Empezar»."""
    session_id, token = guided(env, protocol(env, list(steps), **options))
    return session_id, token


def test_un_protocolo_solo_de_reconocimiento_espera_empezar_sin_calibrar_ni_pedir_la_camara(env):  # noqa: F811
    sad = sad_stimulus(env)
    env.guided.resolve_model = no_model          # sin cámara no se necesita el modelo facial
    session_id, token = ready(env, recognition(sad), recognition(sad))
    current = state(env, session_id)
    assert current["phase"] == "ready" and current["step_index"] is None
    assert current["uses_camera"] is False and current["calibration"]["state"] == "none"
    shown = view(env, token).json()
    assert shown["message"] == "En un momento empezamos." and shown["uses_camera"] is False
    assert shown["capture_frames"] is False and "recognition" not in shown
    # El tiempo del primer paso no corre mientras espera.
    wait(env, 60)
    assert state(env, session_id)["phase"] == "ready"
    # No hay calibración que iniciar ni paso que saltar, y los cuadros se descartan sin analizarlos.
    assert post(env, session_id, "calibration").status_code == 409
    assert post(env, session_id, "skip").status_code == 409
    assessed = env.frames_assessed
    assert frame(env, token).json() == {"received": True}
    assert env.frames_assessed == assessed
    # «Empezar» lleva al primer paso; solo una vez y solo quien conduce.
    assert post(env, session_id, "start", user=env.user_2).status_code in (403, 404)
    assert post(env, session_id, "start").json() == {"phase": "stimuli"}
    assert post(env, session_id, "start").status_code == 409
    current = state(env, session_id)
    assert current["step_index"] == 0 and current["remaining_seconds"] == 10
    shown = view(env, token).json()
    assert shown["recognition"] is not None and shown["capture_frames"] is False
    frame(env, token)
    assert env.frames_assessed == assessed
    session = env.sessions.get_session(session_id)
    assert session.emotion_model_id is None and session.emotion_model_version is None


def test_un_protocolo_solo_de_reconocimiento_avanza_y_termina(env):  # noqa: F811
    sad = sad_stimulus(env)
    emotional, _ = stimuli(env)
    session_id, token = ready(env, recognition(sad), recognition(emotional, exposure=4))
    post(env, session_id, "start")
    wait(env, 2)
    assert answer(env, token, "sadness").status_code == 200
    wait(env, 2.1)                                                     # pausa tras responder
    assert state(env, session_id)["step_index"] == 1
    wait(env, 6.5)                                                     # vence sin respuesta y pausa
    finished = state(env, session_id)
    assert finished["phase"] == "finished"
    assert [item["step_index"] for item in finished["steps_log"]] == [0, 1]
    assert [item["outcome"] for item in finished["recognition_results"]] == ["answered", "timed_out"]
    assert finished["captures"] == [] and finished["practice_results"] == []
    assert env.sessions.get_session(session_id).state.value == "completed"
    assert view(env, token).status_code == 404


def test_sin_camara_el_cuestionario_previo_lleva_a_empezar(env):  # noqa: F811
    sad = sad_stimulus(env)
    pre = create_questionnaire(env, env.user_1,
                               items=[{"id": "a", "kind": "faces", "text": "¿Cómo estás?", "required": True}])
    post_q = create_questionnaire(env, env.user_1, items=[{"id": "b", "kind": "short_text", "text": "¿Algo más?"}])
    session_id, token = ready(env, recognition(sad, exposure=3), pre=pre, post=post_q)
    assert state(env, session_id)["phase"] == "pre_questionnaire"
    assert view(env, token).json()["capture_frames"] is False
    env.client.post(f"/sessions/{session_id}/questionnaires/pre", headers=headers(env, env.user_1),
                    json={"answers": {"a": 3}, "entry_mode": "participant"})
    advanced = post(env, session_id, "advance").json()
    assert advanced["phase"] == "ready"
    assert post(env, session_id, "start").json() == {"phase": "stimuli"}
    wait(env, 5.5)                                                     # vence y pausa
    assert state(env, session_id)["phase"] == "post_questionnaire"
    env.client.post(f"/sessions/{session_id}/questionnaires/post", headers=headers(env, env.user_1),
                    json={"answers": {}, "entry_mode": "conductor"})
    assert post(env, session_id, "advance").json()["phase"] == "finished"
    assert env.sessions.get_session(session_id).state.value == "completed"


def test_una_sesion_sin_camara_se_puede_saltar_y_detener(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = ready(env, recognition(sad), recognition(sad))
    post(env, session_id, "start")
    wait(env, 1)
    assert post(env, session_id, "skip").status_code == 200
    wait(env, 1)
    assert env.client.post(f"/participant-view/{token}/stop").json() == {"stopped": True}
    stopped = state(env, session_id)
    assert stopped["phase"] == "stopped" and stopped["stop_reason"] == "participant"
    outcomes = [item.outcome for item in env.guided.repository.list_recognition_results(session_id)]
    assert outcomes == [RecognitionOutcome.SKIPPED, RecognitionOutcome.STOPPED]


# --- Protocolos con cámara: sin cambios -------------------------------------------------


def test_detener_mientras_espera_empezar(env):  # noqa: F811
    sad = sad_stimulus(env)
    session_id, token = ready(env, recognition(sad))
    assert post(env, session_id, "stop", {"reason": "conductor"}).json() == {"phase": "stopped"}
    assert env.guided.repository.list_recognition_results(session_id) == ()
    assert post(env, session_id, "start").status_code == 409


def test_un_protocolo_con_practica_facial_sigue_calibrando(env):  # noqa: F811
    session_id, token = guided(env, practice_protocol(env, ProtocolStep.practice("happiness", 2, 20)))
    current = state(env, session_id)
    assert current["phase"] == "calibration" and current["uses_camera"] is True
    assert "uses_camera" not in view(env, token).json()      # con cámara, la vista no cambia
    assert env.sessions.get_session(session_id).emotion_model_id == "hsemotion_enet_b0_8_best_afew"
    env.frame_result = NEUTRAL
    calibrate(env, session_id, token)
    assert state(env, session_id)["phase"] == "stimuli"
    assert view(env, token).json()["capture_frames"] is True
    send(env, token, HAPPY, count=6)
    [result] = env.guided.repository.list_practice_results(session_id)
    assert result.outcome is PracticeOutcome.ACHIEVED and result.relative_to_calibration is True
    wait(env, 3)
    assert state(env, session_id)["phase"] == "finished"


def test_un_protocolo_mixto_calibra_antes_del_primer_paso(env):  # noqa: F811
    sad = sad_stimulus(env)
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [recognition(sad), step(emotional)]))
    assert state(env, session_id)["phase"] == "calibration"
    assert state(env, session_id)["uses_camera"] is True
    assert post(env, session_id, "start").status_code == 409          # con cámara se empieza calibrando
    calibrate(env, session_id, token)
    current = state(env, session_id)
    assert current["phase"] == "stimuli" and current["step_index"] == 0
    # El reconocimiento sigue sin analizar la cámara dentro de una sesión con cámara.
    assert view(env, token).json()["capture_frames"] is False


def test_un_protocolo_con_camara_sigue_necesitando_el_modelo_facial(env):  # noqa: F811
    emotional, _ = stimuli(env)
    env.guided.resolve_model = no_model
    item = protocol(env, [step(emotional)])
    with pytest.raises(AssertionError, match="modelo facial no est"):
        guided(env, item)                        # la preparación responde 409 con ese mensaje
