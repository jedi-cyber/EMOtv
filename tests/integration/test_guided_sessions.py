"""Sesión con protocolo: cuestionario previo, calibración, imágenes del
protocolo, calidad de captura, marcadores y pantalla de la persona; y sesión sin
protocolo con lectura en vivo (SQLite en memoria, analizador falso, sin modelos
ni imágenes de personas)."""
from __future__ import annotations

from datetime import timedelta
import json

from sqlalchemy import LargeBinary, inspect, select

from emotv.domain.guided_session import ABSTRACT_NOTICE, FrameAssessment, QualityIssue
from emotv.infrastructure.persistence.models import SessionMarkerRecord, VerbalResponseRecord
from emotv.shared.security.field_encryption import FieldCipher
from emotv.application.commitment_service import load_text
from tests.integration.test_protocols_and_stimuli import approve, upload_stimulus
from tests.integration.test_privacy_accounts import KEY, accept_commitment, env, headers  # noqa: F401
from tests.integration.test_questionnaires import create as create_questionnaire

FRAME = b"cuadro-jpeg-de-prueba"
GOOD = FrameAssessment((), "happiness", 0.8, {"happiness": 0.8, "neutral": 0.2})
RESULT_WORDS = ("happiness", "neutral", "emotion", "confidence", "distribution", "quality", "probab", "note",
                "captures", "markers", "calibrated")


def step(stimulus, exposure=6, capture=2, verbal=False, before=False):
    return {"stimulus_id": stimulus["id"], "exposure_seconds": exposure, "capture_after_seconds": capture,
            "record_verbal_response": verbal, "shown_before_analyzer": before}


def stimuli(env):  # noqa: F811
    emotional = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Paisaje"))
    abstract = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Forma", kind="abstract",
                                                          not_a_projective_test="true"))
    return emotional, abstract


def protocol(env, steps, pre=None, post=None, for_children=False):  # noqa: F811
    body = {"name": "Secuencia", "description": "", "for_children": for_children, "steps": steps,
            "pre_questionnaire_id": pre["id"] if pre else None, "post_questionnaire_id": post["id"] if post else None}
    response = env.client.post("/protocols", headers=headers(env, env.user_1), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def guided(env, protocol_item=None, session_type=None):  # noqa: F811
    """Inicia la sesión con su única confirmación y prepara la pantalla de la persona."""
    accept_commitment(env, env.user_1)
    env.commitments.accept(env.user_1, load_text("child_notice").version, "child_notice")
    body = {"authorization_confirmed": True}
    if protocol_item is not None:
        body["protocol_id"] = protocol_item["id"]
    body["session_type"] = session_type or ("propia" if protocol_item is not None
                                            and not protocol_item["for_children"] else None)
    body = {key: value for key, value in body.items() if value is not None}
    session = env.client.post("/sessions", headers=headers(env, env.user_1), json=body)
    assert session.status_code == 201, session.text
    created = env.client.post(f"/guided-sessions/{session.json()['id']}", headers=headers(env, env.user_1))
    assert created.status_code == 201, created.text
    return session.json()["id"], created.json()["view_token"]


def state(env, session_id, user=None):  # noqa: F811
    response = env.client.get(f"/guided-sessions/{session_id}", headers=headers(env, user or env.user_1))
    assert response.status_code == 200, response.text
    return response.json()


def post(env, session_id, action, body=None, user=None):  # noqa: F811
    return env.client.post(f"/guided-sessions/{session_id}/{action}", headers=headers(env, user or env.user_1),
                           json=body)


def view(env, token):  # noqa: F811
    return env.client.get(f"/participant-view/{token}")


def frame(env, token):  # noqa: F811
    return env.client.post(f"/participant-view/{token}/frames", content=FRAME, headers={"Content-Type": "image/jpeg"})


def wait(env, seconds):  # noqa: F811
    env.clock.now += timedelta(seconds=seconds)


def calibrate(env, session_id, token):  # noqa: F811
    assert post(env, session_id, "calibration").status_code == 200
    for _ in range(5):
        assert frame(env, token).json() == {"received": True}
        wait(env, 0.6)
    wait(env, 0.5)
    frame(env, token)


# --- Inicio y orden de la sesión -----------------------------------------------------

def test_the_confirmation_happens_once_at_the_start(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional)]))
    # No hay una segunda confirmación dentro de la sesión: empieza en la calibración.
    assert state(env, session_id)["phase"] == "calibration"
    assert post(env, session_id, "confirm", {"authorization_confirmed": True}).status_code in (404, 405)
    assert state(env, session_id)["captures"] == []
    child_session, _ = guided(env, protocol(env, [step(emotional)], for_children=True))
    current = state(env, child_session)
    assert current["phase"] == "calibration" and current["audience"] == "infantil"
    assert current["session_code"].startswith("S-")


def test_a_session_without_a_confirmed_authorization_cannot_be_prepared(env):  # noqa: F811
    emotional, _ = stimuli(env)
    item = protocol(env, [step(emotional)])
    accept_commitment(env, env.user_1)
    session = env.sessions.start_session(student_id=env.student_1.id, owner_user_id=env.user_1.id,
                                         protocol_id=item["id"])
    assert post(env, session.id, "").status_code == 409


def test_without_a_protocol_the_session_is_the_live_reading(env):  # noqa: F811
    session_id, token = guided(env, session_type="infantil")
    current = state(env, session_id)
    assert current["phase"] == "calibration" and current["has_protocol"] is False and current["step_count"] == 0
    calibrate(env, session_id, token)
    assert state(env, session_id)["phase"] == "live"
    # Un niño sin protocolo no ve ninguna imagen ni cuestionario: solo la lectura.
    shown = view(env, token).json()
    assert shown["stimulus"] is None and shown["capture_frames"] is True
    assert env.client.get(f"/participant-view/{token}/stimulus").status_code in (404, 409)
    assert env.client.get(f"/sessions/{session_id}/questionnaires/pre",
                          headers=headers(env, env.user_1)).status_code in (404, 409)
    for _ in range(3):
        frame(env, token)
        wait(env, 3)
    captures = state(env, session_id)["captures"]
    assert len(captures) >= 2 and all(item["stimulus_id"] is None for item in captures)
    finished = env.guided.finish_live(env.user_1, session_id)
    assert finished.phase.value == "finished"
    session = env.sessions.get_session(session_id)
    assert session.state.value == "completed" and session.initial_emotion == "happiness"


def test_the_pre_questionnaire_goes_before_calibration(env):  # noqa: F811
    emotional, _ = stimuli(env)
    pre = create_questionnaire(env, env.user_1, items=[{"id": "a", "kind": "faces", "text": "¿Cómo estás?", "required": True}])
    session_id, token = guided(env, protocol(env, [step(emotional)], pre=pre))
    assert state(env, session_id)["phase"] == "pre_questionnaire"
    assert post(env, session_id, "calibration").status_code == 409
    assert post(env, session_id, "advance").status_code == 409
    assert view(env, token).json()["capture_frames"] is False
    answer = env.client.post(f"/sessions/{session_id}/questionnaires/pre", headers=headers(env, env.user_1),
                             json={"answers": {"a": 3}, "entry_mode": "participant"})
    assert answer.status_code == 201
    assert post(env, session_id, "advance").json()["phase"] == "calibration"


def test_the_flow_follows_the_protocol(env):  # noqa: F811
    emotional, abstract = stimuli(env)
    post_q = create_questionnaire(env, env.user_1, items=[{"id": "b", "kind": "short_text", "text": "¿Algo más?"}])
    steps = [step(abstract, exposure=4, verbal=True, before=True), step(emotional, exposure=6, capture=2),
             step(abstract, exposure=8, capture=2, verbal=True)]
    session_id, token = guided(env, protocol(env, steps, post=post_q), "adulto")
    # Abstracta antes del analizador: se muestra, sin capturas.
    current = state(env, session_id)
    assert current["phase"] == "before_analyzer" and current["step_index"] == 0
    assert view(env, token).json()["stimulus"] is not None and view(env, token).json()["capture_frames"] is False
    assert env.client.get(f"/participant-view/{token}/stimulus").headers["content-type"] == "image/png"
    frame(env, token)
    assert post(env, session_id, "verbal-responses", {"step_index": 0, "text": "Una mariposa"}).status_code == 201
    wait(env, 4)
    assert state(env, session_id)["phase"] == "calibration"
    calibrate(env, session_id, token)
    current = state(env, session_id)
    assert current["phase"] == "stimuli" and current["step_index"] == 1
    # Emocional: captura automática a los 2 s.
    frame(env, token)
    assert state(env, session_id)["captures"] == []
    wait(env, 2)
    frame(env, token)
    captures = state(env, session_id)["captures"]
    assert len(captures) == 1 and captures[0]["quality"] == "good" and captures[0]["emotion"] == "happiness"
    assert captures[0]["seconds_since_stimulus"] == 2.0 and captures[0]["stimulus_id"] == emotional["id"]
    assert captures[0]["emotion_model_id"] == "hsemotion_enet_b0_8_best_afew"
    wait(env, 4)
    # Abstracta durante la sesión: varias capturas durante la exposición.
    assert state(env, session_id)["step_index"] == 2
    for _ in range(3):
        wait(env, 2.5)
        frame(env, token)
    abstract_captures = [item for item in state(env, session_id)["captures"] if item["step_index"] == 2]
    assert len(abstract_captures) >= 2
    wait(env, 8)
    assert state(env, session_id)["phase"] == "post_questionnaire"
    assert post(env, session_id, "advance").status_code == 409
    env.client.post(f"/sessions/{session_id}/questionnaires/post", headers=headers(env, env.user_1),
                    json={"answers": {}, "entry_mode": "conductor"})
    assert post(env, session_id, "advance").json()["phase"] == "finished"
    assert env.sessions.get_session(session_id).state.value == "completed"
    assert [item["step_index"] for item in state(env, session_id)["steps_log"]] == [0, 1, 2]
    # Terminada, el enlace de la pantalla de la persona deja de valer.
    assert view(env, token).status_code == 404


def test_a_low_quality_capture_is_retried_and_then_flagged(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional, exposure=10, capture=2), step(emotional, exposure=5)]))
    calibrate(env, session_id, token)
    env.frame_result = FrameAssessment((QualityIssue.OFF_CENTER, QualityIssue.TOO_DARK), "neutral", 0.6, {"neutral": 0.6})
    wait(env, 2)
    frame(env, token)
    current = state(env, session_id)
    assert current["captures"] == [] and current["capture_status"] == ["off_center", "too_dark"]  # reintentando
    wait(env, 3)
    frame(env, token)
    capture = state(env, session_id)["captures"][0]
    assert capture["quality"] == "flagged" and capture["quality_issues"] == ["off_center", "too_dark"]
    assert capture["emotion"] == "neutral"
    # Sin ningún cuadro, la captura vencida queda marcada como "sin cuadro".
    wait(env, 5)
    assert state(env, session_id)["step_index"] == 1
    wait(env, 5)
    flagged = state(env, session_id)["captures"][-1]
    assert flagged["step_index"] == 1 and flagged["quality_issues"] == ["no_frame"] and flagged["emotion"] is None


# --- Pantalla de la persona, paradas y marcadores --------------------------------------

def test_the_persons_screen_never_receives_results(env):  # noqa: F811
    emotional, abstract = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional), step(abstract, exposure=6, verbal=True)]))
    responses = [view(env, token).json()]
    post(env, session_id, "markers", {"kind": "note", "note": "Miró la ventana"})
    responses.append(view(env, token).json())
    calibrate(env, session_id, token)
    for _ in range(6):
        wait(env, 2)
        responses.append(frame(env, token).json())
        responses.append(view(env, token).json())
    assert state(env, session_id)["captures"]  # hubo capturas...
    text = json.dumps(responses)
    for word in RESULT_WORDS:
        assert word not in text, word  # ...pero la pantalla de la persona no las ve
    allowed = {"phase", "message", "stimulus", "remaining_seconds", "capture_frames", "frame_interval_ms", "abstract_notice"}
    # Al terminar, el enlace deja de valer y solo responde que no existe.
    assert all(set(item) <= allowed or item == {"received": True} or set(item) == {"detail"} for item in responses)


def test_the_person_can_stop_and_the_conductor_can_skip_or_end(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional), step(emotional), step(emotional)]))
    calibrate(env, session_id, token)
    assert post(env, session_id, "skip").status_code == 200
    current = state(env, session_id)
    assert current["step_index"] == 1 and current["steps_log"][0]["skipped"] is True
    assert env.client.post(f"/participant-view/{token}/stop").json() == {"stopped": True}
    stopped = state(env, session_id)
    assert stopped["phase"] == "stopped" and stopped["stop_reason"] == "participant"
    assert env.sessions.get_session(session_id).state.value == "cancelled"
    assert view(env, token).status_code == 404

    second, _ = guided(env, protocol(env, [step(emotional)]))
    # El marcador "pidió parar" termina la sesión de inmediato.
    assert post(env, second, "markers", {"kind": "asked_to_stop"}).status_code == 201
    assert state(env, second)["stop_reason"] == "participant"

    third, _ = guided(env, protocol(env, [step(emotional)]))
    assert post(env, third, "stop", {"reason": "guardian"}).json()["phase"] == "stopped"
    assert state(env, third)["stop_reason"] == "guardian"


def test_only_the_conductor_controls_and_the_docente_can_review(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional)]))
    for user in (env.docente_a, env.user_2, env.admin):
        assert env.client.get(f"/guided-sessions/{session_id}", headers=headers(env, user)).status_code == 403
        assert post(env, session_id, "skip", user=user).status_code == 403
    assert env.client.get(f"/sessions/{session_id}/guided-results", headers=headers(env, env.docente_a)).status_code == 200
    for user in (env.user_2, env.docente_b, env.admin, env.superadmin):
        assert env.client.get(f"/sessions/{session_id}/guided-results", headers=headers(env, user)).status_code == 403
    assert view(env, "enlace-inventado").status_code == 404


# --- Cifrado, aviso y tabla de capturas ---------------------------------------------------

def test_notes_and_what_the_person_says_are_stored_encrypted(env):  # noqa: F811
    _, abstract = stimuli(env)
    session_id, _ = guided(env, protocol(env, [step(abstract, verbal=True, before=True)]))
    assert post(env, session_id, "markers", {"kind": "note", "note": "Miró la ventana"}).status_code == 201
    assert post(env, session_id, "markers", {"kind": "note"}).status_code == 422
    assert post(env, session_id, "verbal-responses", {"step_index": 0, "text": "Una mariposa"}).status_code == 201
    with env.factory() as db:
        note = db.scalar(select(SessionMarkerRecord.note_encrypted).where(SessionMarkerRecord.kind == "note"))
        said = db.scalar(select(VerbalResponseRecord.text_encrypted))
    assert "ventana" not in note and "mariposa" not in said
    assert FieldCipher([KEY]).decrypt(note) == "Miró la ventana" and FieldCipher([KEY]).decrypt(said) == "Una mariposa"
    current = state(env, session_id)
    assert current["markers"][0]["note"] == "Miró la ventana"
    assert current["verbal_responses"][0]["text"] == "Una mariposa"


def test_the_abstract_notice_always_appears(env):  # noqa: F811
    emotional, abstract = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(abstract, exposure=4, before=True), step(emotional)]))
    assert state(env, session_id)["abstract_notice"] == ABSTRACT_NOTICE
    assert view(env, token).json()["abstract_notice"] == ABSTRACT_NOTICE
    results = env.client.get(f"/sessions/{session_id}/guided-results", headers=headers(env, env.docente_a)).json()
    assert results["abstract_notice"] == ABSTRACT_NOTICE
    only_emotional, other_token = guided(env, protocol(env, [step(emotional)]))
    assert state(env, only_emotional)["abstract_notice"] is None


def test_the_capture_table_has_no_images_or_identity_data(env):  # noqa: F811
    forbidden = ("image", "imagen", "frame", "cuadro", "photo", "foto", "jpeg", "png", "name", "dni", "email",
                 "phone", "guardian", "tutor", "code")
    for table in ("expression_captures", "session_markers", "verbal_responses", "guided_runs"):
        columns = inspect(env.engine).get_columns(table)
        names = [column["name"] for column in columns]
        assert not [name for name in names if any(word in name for word in forbidden)], table
        assert not [column for column in columns if isinstance(column["type"], LargeBinary)], table
    expected = {"session_id", "captured_at", "emotion_model_id", "emotion", "confidence", "distribution", "quality",
                "stimulus_id", "seconds_since_stimulus"}
    assert expected <= {column["name"] for column in inspect(env.engine).get_columns("expression_captures")}


def test_deleting_the_session_removes_the_guided_records(env):  # noqa: F811
    emotional, abstract = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional, exposure=6, capture=2),
                                                   step(abstract, verbal=True)]), "adulto")
    calibrate(env, session_id, token)
    wait(env, 2)
    frame(env, token)
    post(env, session_id, "markers", {"kind": "laughed"})
    wait(env, 4)
    post(env, session_id, "verbal-responses", {"step_index": 1, "text": "Una nube"})
    post(env, session_id, "stop", {"reason": "conductor"})
    response = env.client.post(f"/sessions/{session_id}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 200, response.text
    certificate = response.json()
    counts = certificate["counts"]
    assert certificate["verified"] and counts["expression_captures"] >= 1
    assert counts["session_markers"] == 1 and counts["verbal_responses"] == 1 and counts["guided_runs"] == 1
    assert env.guided.repository.get_run(session_id) is None
