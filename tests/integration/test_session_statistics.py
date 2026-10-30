"""Estadísticas agregadas con datos sintéticos: cuentan sesiones, no personas,
solo con las sesiones a las que la cuenta tiene acceso (SQLite en memoria, sin
servicios externos ni imágenes)."""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from emotv.domain.guided_session import CaptureQuality, ExpressionCapture, QualityIssue
from emotv.domain.questionnaire import QuestionnaireResponse
from emotv.domain.session import EmotionalSession
from tests.integration.test_privacy_accounts import NOW, env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import audit_actions, create_protocol, upload_stimulus
from tests.integration.test_questionnaires import create as create_questionnaire


def session(env, owner, *, day=0, state="completed", minutes=10, audience="adulto", protocol=None):  # noqa: F811
    started = NOW + timedelta(days=day)
    item = EmotionalSession(
        id=str(uuid4()), started_at=started, state=state, owner_user_id=owner.id, session_type=audience,
        completed_at=started + timedelta(minutes=minutes) if state in ("completed", "cancelled") else None,
        protocol_id=protocol["id"] if protocol else None,
        **({} if protocol or state != "completed" else
           {"initial_emotion": "neutral", "emotion_confidence": 0.6, "exercise_result": "skipped"}))
    return env.sessions.repository.save(item)


def capture(env, item, emotion, *, flagged=False, step=0, stimulus=None, second=1):  # noqa: F811
    env.guided.repository.add_capture(ExpressionCapture(
        id=str(uuid4()), session_id=item.id, captured_at=item.started_at + timedelta(seconds=second),
        emotion_model_id="hsemotion_enet_b0_8_best_afew", emotion_model_version="prueba",
        quality=CaptureQuality.FLAGGED if flagged else CaptureQuality.GOOD,
        quality_issues=(QualityIssue.TOO_DARK,) if flagged else (), step_index=step,
        stimulus_id=stimulus["id"] if stimulus else None, seconds_since_stimulus=float(second),
        emotion=emotion, confidence=0.7, distribution={emotion: 0.7}))


def statistics(env, user, **params):  # noqa: F811
    return env.client.get("/statistics", headers=headers(env, user), params=params)


def test_percentages_and_counts_use_only_good_quality_captures(env):  # noqa: F811
    first, second = session(env, env.user_1), session(env, env.user_1, day=1)
    for emotion in ("happiness", "happiness", "neutral"):
        capture(env, first, emotion)
    capture(env, first, "sadness", flagged=True)  # mala calidad: no cuenta
    capture(env, second, "happiness")
    body = statistics(env, env.user_1).json()
    rows = {row["expression"]: row for row in body["expressions"]["rows"]}
    assert list(rows) == ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]
    assert body["expressions"]["counted_captures"] == 4 and body["expressions"]["excluded_captures"] == 1
    assert (rows["happiness"]["captures"], rows["happiness"]["percent"], rows["happiness"]["sessions"]) == (3, 75.0, 2)
    assert (rows["neutral"]["captures"], rows["neutral"]["percent"], rows["neutral"]["sessions"]) == (1, 25.0, 1)
    assert rows["sadness"] == {"expression": "sadness", "captures": 0, "percent": 0.0, "sessions": 0}


def test_summary_counts_completed_and_interrupted_sessions_and_the_average_duration(env):  # noqa: F811
    session(env, env.user_1, minutes=10)
    session(env, env.user_1, minutes=20)
    session(env, env.user_1, state="cancelled", minutes=3)
    session(env, env.user_1, state="in_progress")
    summary = statistics(env, env.user_1).json()["sessions"]
    assert summary == {"total": 4, "completed": 2, "interrupted": 1, "average_duration_seconds": 900.0}


def test_filters_by_dates_protocol_and_audience(env):  # noqa: F811
    stimulus = upload_stimulus(env, env.docente_a)
    protocol = create_protocol(env, env.user_1, stimulus, name="Secuencia")
    session(env, env.user_1, day=0, audience="propia")
    session(env, env.user_1, day=2, audience="infantil")
    session(env, env.user_1, day=4, protocol=protocol)
    total = lambda **params: statistics(env, env.user_1, **params).json()["sessions"]["total"]  # noqa: E731
    first_day = NOW.date()
    assert total() == 3
    assert total(date_from=str(first_day + timedelta(days=1))) == 2
    assert total(date_from=str(first_day + timedelta(days=1)), date_to=str(first_day + timedelta(days=3))) == 1
    assert total(audience="infantil") == 1 and total(audience="propia") == 1
    assert total(protocol=protocol["family_id"]) == 1 and total(protocol="none") == 2
    assert statistics(env, env.user_1).json()["protocols"] == [{"family_id": protocol["family_id"], "name": "Secuencia"}]
    assert statistics(env, env.user_1, date_from="2026-12-01", date_to="2026-11-01").status_code == 422


def test_emotional_stimuli_count_how_often_the_expected_expression_matched(env):  # noqa: F811
    happy = upload_stimulus(env, env.docente_a, title="Alegre")  # espera felicidad
    protocol = create_protocol(env, env.user_1, happy, happy)
    for estimated in ("happiness", "sadness"):
        item = session(env, env.user_1, protocol=protocol)
        capture(env, item, "happiness", step=0, stimulus=happy)
        capture(env, item, estimated, step=1, stimulus=happy)
    assert statistics(env, env.user_1).json()["coincidence"] == {"compared": 4, "matched": 3}


def test_a_user_sees_only_their_sessions_and_a_docente_only_their_group(env):  # noqa: F811
    session(env, env.user_1)
    session(env, env.user_1, state="cancelled")
    session(env, env.user_2)
    session(env, env.docente_a)
    assert statistics(env, env.user_1).json()["sessions"]["total"] == 2
    assert statistics(env, env.user_2).json()["sessions"]["total"] == 1
    assert statistics(env, env.user_1, scope="group").status_code == 403
    mine = statistics(env, env.docente_a).json()
    assert mine["sessions"]["total"] == 1 and "by_user" not in mine
    group = statistics(env, env.docente_a, scope="group").json()
    assert group["sessions"]["total"] == 2
    assert group["by_user"] == [{"email": "usuario1@example.com", "sessions": 2, "completed": 1, "interrupted": 1}]
    assert statistics(env, env.docente_b, scope="group").json()["by_user"][0]["email"] == "usuario2@example.com"


def test_the_administration_has_no_access_and_every_query_is_audited(env):  # noqa: F811
    session(env, env.user_1)
    for user in (env.admin, env.superadmin):
        assert statistics(env, user).status_code == 403
    statistics(env, env.user_1)
    statistics(env, env.docente_a, scope="group")
    actions = audit_actions(env, resource_type="session_statistics")
    assert sorted(actions) == sorted([("view", "session_statistics", "denied")] * 2
                                     + [("view", "session_statistics", "success")] * 2)


def test_questionnaire_distribution_counts_choices_and_hides_text_answers(env):  # noqa: F811
    questionnaire = create_questionnaire(env, env.user_1, items=[
        {"id": "s", "kind": "scale", "text": "¿Qué tan tranquilo?", "scale_points": 3, "min_label": "Poco",
         "max_label": "Mucho"},
        {"id": "o", "kind": "single_choice", "text": "¿Dormiste bien?", "options": ["Sí", "No"]},
        {"id": "m", "kind": "multiple_choice", "text": "¿Qué hiciste?", "options": ["Leer", "Correr", "Dormir"]},
        {"id": "t", "kind": "short_text", "text": "Cuéntanos algo"},
    ])
    answers = [{"s": 3, "o": "Sí", "m": ["Leer", "Correr"], "t": "Texto privado uno"},
               {"s": 3, "o": "No", "m": ["Leer"], "t": "Texto privado dos"},
               {"s": 1, "o": "Sí", "m": []}]
    for index, given in enumerate(answers):
        item = session(env, env.user_1, day=index)
        env.questionnaires.responses.add(QuestionnaireResponse(
            id=str(uuid4()), session_id=item.id, questionnaire_id=questionnaire["id"], moment="pre", answers=given,
            entry_mode="participant", recorded_by_user_id=env.user_1.id, submitted_at=item.started_at))
    listed = statistics(env, env.user_1).json()
    assert listed["questionnaires"] == [{"id": questionnaire["id"], "title": questionnaire["title"], "version": 1,
                                         "responses": 3}]
    assert listed["questionnaire"] is None
    response = statistics(env, env.user_1, questionnaire_id=questionnaire["id"])
    detail = response.json()["questionnaire"]
    scale, choice, multiple, text = detail["questions"]
    assert scale["counts"] == [{"label": "1", "count": 1}, {"label": "2", "count": 0}, {"label": "3", "count": 2}]
    assert choice["counts"] == [{"label": "Sí", "count": 2}, {"label": "No", "count": 1}]
    assert multiple["counts"] == [{"label": "Leer", "count": 2}, {"label": "Correr", "count": 1},
                                  {"label": "Dormir", "count": 0}]
    assert (multiple["answered"], multiple["unanswered"]) == (2, 1)
    # El texto no se expone: solo cuántas respuestas hubo.
    assert (text["counts"], text["answered"], text["unanswered"]) == (None, 2, 1)
    assert "Texto privado" not in response.text
    # Otro usuario no ve ese cuestionario ni sus respuestas.
    assert statistics(env, env.user_2, questionnaire_id=questionnaire["id"]).json()["questionnaire"] is None


def test_the_fixed_notice_and_the_few_sessions_notice(env):  # noqa: F811
    for day in range(4):
        session(env, env.user_1, day=day)
    body = statistics(env, env.user_1).json()
    assert body["notice"] == ("Estas estadísticas cuentan sesiones, no personas, y son estimaciones. No permiten "
                              "sacar conclusiones sobre ninguna persona.")
    assert body["few_sessions"] is True and body["few_sessions_notice"] == "Hay pocas sesiones para sacar conclusiones."
    session(env, env.user_1, day=5)
    body = statistics(env, env.user_1).json()
    assert body["few_sessions"] is False and body["few_sessions_notice"] is None
