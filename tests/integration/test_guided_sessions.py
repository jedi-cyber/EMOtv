"""Sesión guiada: confirmación, cuestionario previo, calibración, estímulos del
protocolo, calidad de captura, marcadores y vista del participante (SQLite en
memoria, analizador falso, sin modelos ni imágenes de personas)."""
from __future__ import annotations

from datetime import timedelta
import json

from sqlalchemy import LargeBinary, inspect, select

from emotv.domain.guided_session import ABSTRACT_NOTICE, FrameAssessment, QualityIssue
from emotv.infrastructure.persistence.models import SessionMarkerRecord, VerbalResponseRecord
from emotv.shared.security.field_encryption import FieldCipher
from tests.integration.test_participant_practices import approve, authorize, upload_stimulus
from tests.integration.test_privacy_accounts import KEY, accept_commitment, env, headers, register  # noqa: F401
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
    item = response.json()
    if for_children:
        env.client.post(f"/protocols/{item['id']}/approve", headers=headers(env, env.docente_a))
    return item


def guided(env, protocol_item, participant=None):  # noqa: F811
    accept_commitment(env, env.user_1)
    body = {"session_type": "propia", "protocol_id": protocol_item["id"]}
    if participant is not None:
        kind = "participante_infantil" if participant["kind"] == "child" else "participante_adulto"
        body.update(session_type=kind, participant_id=participant["id"])
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


# --- Confirmación y orden de la sesión ----------------------------------------------

def test_it_does_not_start_without_the_confirmation(env):  # noqa: F811
    emotional, _ = stimuli(env)
    adult = register(env, env.user_1)
    authorize(env, env.user_1, adult)
    session_id, token = guided(env, protocol(env, [step(emotional)]), adult)
    assert state(env, session_id)["phase"] == "confirmation"
    assert view(env, token).json()["capture_frames"] is False
    frame(env, token)
    assert post(env, session_id, "calibration").status_code == 409
    assert post(env, session_id, "advance").status_code == 409
    assert post(env, session_id, "confirm", {"authorization_confirmed": True}).status_code == 422  # sin recordatorio
    assert post(env, session_id, "confirm", {"commitment_reminder": True}).status_code == 422      # sin autorización
    assert post(env, session_id, "confirm", {"commitment_reminder": True,
                                             "authorization_confirmed": True}).json()["phase"] == "calibration"
    assert state(env, session_id)["captures"] == []

    child = register(env, env.user_1, kind="child", age=9)
    authorize(env, env.user_1, child, child_assent=True)
    child_session, _ = guided(env, protocol(env, [step(emotional)], for_children=True), child)
    for body in ({"commitment_reminder": True, "guardian_present": True},
                 {"commitment_reminder": True, "child_assent": True},
                 {"commitment_reminder": True, "authorization_confirmed": True}):
        assert post(env, child_session, "confirm", body).status_code == 422, body
    assert post(env, child_session, "confirm", {"commitment_reminder": True, "guardian_present": True,
                                                "child_assent": True}).status_code == 200


def test_the_pre_questionnaire_goes_before_calibration(env):  # noqa: F811
    emotional, _ = stimuli(env)
    pre = create_questionnaire(env, env.user_1, items=[{"id": "a", "kind": "faces", "text": "¿Cómo estás?", "required": True}])
    session_id, token = guided(env, protocol(env, [step(emotional)], pre=pre))
    post(env, session_id, "confirm", {"commitment_reminder": True})
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
    adult = register(env, env.user_1)
    authorize(env, env.user_1, adult)
    steps = [step(abstract, exposure=4, verbal=True, before=True), step(emotional, exposure=6, capture=2),
             step(abstract, exposure=8, capture=2, verbal=True)]
    session_id, token = guided(env, protocol(env, steps, post=post_q), adult)
    post(env, session_id, "confirm", {"commitment_reminder": True, "authorization_confirmed": True})
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
    # Terminada, el enlace del participante deja de valer.
    assert view(env, token).status_code == 404


def test_a_low_quality_capture_is_retried_and_then_flagged(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional, exposure=10, capture=2), step(emotional, exposure=5)]))
    post(env, session_id, "confirm", {"commitment_reminder": True})
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


# --- Vista del participante, paradas y marcadores --------------------------------------

def test_the_participant_view_never_receives_results(env):  # noqa: F811
    emotional, abstract = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional), step(abstract, exposure=6, verbal=True)]))
    responses = [view(env, token).json()]
    post(env, session_id, "confirm", {"commitment_reminder": True})
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
        assert word not in text, word  # ...pero la vista del participante no las ve
    allowed = {"phase", "message", "stimulus", "remaining_seconds", "capture_frames", "frame_interval_ms", "abstract_notice"}
    # Al terminar, el enlace deja de valer y solo responde que no existe.
    assert all(set(item) <= allowed or item == {"received": True} or set(item) == {"detail"} for item in responses)


def test_the_participant_can_stop_and_the_conductor_can_skip_or_end(env):  # noqa: F811
    emotional, _ = stimuli(env)
    session_id, token = guided(env, protocol(env, [step(emotional), step(emotional), step(emotional)]))
    post(env, session_id, "confirm", {"commitment_reminder": True})
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
    post(env, second, "confirm", {"commitment_reminder": True})
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

def test_notes_and_what_the_participant_says_are_stored_encrypted(env):  # noqa: F811
    _, abstract = stimuli(env)
    session_id, _ = guided(env, protocol(env, [step(abstract, verbal=True, before=True)]))
    post(env, session_id, "confirm", {"commitment_reminder": True})
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
    post(env, session_id, "confirm", {"commitment_reminder": True})
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


def test_deleting_the_participant_removes_the_guided_records(env):  # noqa: F811
    emotional, abstract = stimuli(env)
    adult = register(env, env.user_1)
    authorize(env, env.user_1, adult)
    session_id, token = guided(env, protocol(env, [step(emotional, exposure=6, capture=2),
                                                   step(abstract, verbal=True)]), adult)
    post(env, session_id, "confirm", {"commitment_reminder": True, "authorization_confirmed": True})
    calibrate(env, session_id, token)
    wait(env, 2)
    frame(env, token)
    post(env, session_id, "markers", {"kind": "laughed"})
    wait(env, 4)
    post(env, session_id, "verbal-responses", {"step_index": 1, "text": "Una nube"})
    certificate = env.client.post(f"/participants/{adult['id']}/delete", headers=headers(env, env.docente_a)).json()
    counts = certificate["counts"]
    assert certificate["verified"] and counts["expression_captures"] >= 1
    assert counts["session_markers"] == 1 and counts["verbal_responses"] == 1 and counts["guided_runs"] == 1
