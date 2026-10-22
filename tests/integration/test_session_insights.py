"""Línea de tiempo, métricas y tendencias por la API: datos de una sesión guiada
real con analizador falso, acceso por can_access_participant y auditoría."""
from __future__ import annotations

from emotv.application.ports.privacy_repositories import AuditFilter
from emotv.domain.guided_session import ABSTRACT_NOTICE, FrameAssessment, QualityIssue
from tests.integration.test_guided_sessions import calibrate, frame, guided, post, protocol, step, stimuli, wait
from tests.integration.test_participant_practices import authorize
from tests.integration.test_privacy_accounts import env, headers, register  # noqa: F401
from tests.integration.test_questionnaires import create as create_questionnaire

GOOD = FrameAssessment((), "happiness", 0.8, {"happiness": 0.8, "neutral": 0.2})


def run_session(env, participant, protocol_item, flagged_second=False):  # noqa: F811
    """Sesión guiada completa: estímulo emocional (esperada: felicidad), otro
    emocional y una abstracta con lo que el participante dijo ver."""
    session_id, token = guided(env, protocol_item, participant)
    post(env, session_id, "confirm", {"commitment_reminder": True, "authorization_confirmed": True})
    if env.client.get(f"/sessions/{session_id}/questionnaires/pre", headers=headers(env, env.user_1)).status_code == 200:
        env.client.post(f"/sessions/{session_id}/questionnaires/pre", headers=headers(env, env.user_1),
                        json={"answers": {"a": 4}, "entry_mode": "participant"})
        post(env, session_id, "advance")
    calibrate(env, session_id, token)
    view = lambda: env.client.get(f"/guided-sessions/{session_id}", headers=headers(env, env.user_1))  # noqa: E731
    # Estímulo 1 (6 s): captura de buena calidad a los 2 s.
    env.frame_result = GOOD
    wait(env, 2)
    frame(env, token)
    post(env, session_id, "markers", {"kind": "laughed"})
    wait(env, 4)
    view()
    # Estímulo 2 (6 s): de buena calidad, o solo con capturas marcadas.
    if flagged_second:
        env.frame_result = FrameAssessment((QualityIssue.TOO_DARK,), "happiness", 0.5, {"happiness": 0.5})
        wait(env, 2)
        frame(env, token)
        wait(env, 3)
        frame(env, token)
        wait(env, 1)
    else:
        env.frame_result = FrameAssessment((), "neutral", 0.6, {"neutral": 0.6})
        wait(env, 2)
        frame(env, token)
        wait(env, 4)
    view()
    # Imagen abstracta (8 s): lo que dice ver y una captura.
    post(env, session_id, "verbal-responses", {"step_index": 2, "text": "Una nube"})
    env.frame_result = GOOD
    wait(env, 2.5)
    frame(env, token)
    wait(env, 6)
    view()
    return session_id


def setup(env):  # noqa: F811
    emotional, abstract = stimuli(env)
    pre = create_questionnaire(env, env.user_1, items=[{"id": "a", "kind": "faces", "text": "¿Cómo estás?", "required": True}])
    item = protocol(env, [step(emotional), step(emotional), step(abstract, exposure=8, verbal=True)], pre=pre)
    adult = register(env, env.user_1)
    authorize(env, env.user_1, adult)
    return item, adult


def test_the_timeline_puts_every_source_on_one_time_axis(env):  # noqa: F811
    item, adult = setup(env)
    session_id = run_session(env, adult, item)
    timeline = env.client.get(f"/sessions/{session_id}/timeline", headers=headers(env, env.docente_a))
    assert timeline.status_code == 200, timeline.text
    lanes = timeline.json()["lanes"]
    assert set(lanes) == {"questionnaires", "stimuli", "captures", "said", "markers", "heart_rate"}
    assert lanes["heart_rate"] == []  # reservado para el sensor
    assert lanes["questionnaires"][0]["answers"] == [{"question": "¿Cómo estás?", "kind": "faces", "answer": 4}]
    assert [entry["step_index"] for entry in lanes["stimuli"]] == [0, 1, 2]
    assert lanes["captures"] and all(entry["time"] is not None for entry in lanes["captures"])
    assert lanes["said"][0]["text"] == "Una nube" and lanes["markers"][0]["kind"] == "laughed"
    times = [entry["start"] for entry in lanes["stimuli"]]
    assert times == sorted(times)


def test_metrics_exclude_low_quality_and_abstract_images_have_no_coincidence(env):  # noqa: F811
    item, adult = setup(env)
    session_id = run_session(env, adult, item, flagged_second=True)
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    totals = metrics["totals"]
    # El primero coincide (felicidad); el segundo solo tiene capturas marcadas: se muestran, no cuentan.
    assert totals["counted"] == 1 and totals["matched"] == 1 and totals["excluded_captures"] >= 1
    assert totals["sentence"] == "En 1 de 1 estímulo la expresión estimada coincidió con la esperada."
    second = metrics["emotional"][1]
    assert second["counted"] is False and second["captures"][0]["quality"] == "flagged"
    abstract = metrics["abstract"][0]
    assert abstract["said"] == "Una nube" and "matches_expected" not in str(abstract)
    assert metrics["abstract_notice"] == ABSTRACT_NOTICE


def test_trends_need_two_comparable_sessions(env):  # noqa: F811
    item, adult = setup(env)
    run_session(env, adult, item)
    single = env.client.get(f"/participants/{adult['id']}/trends", headers=headers(env, env.docente_a)).json()
    assert single["protocols"][0]["comparable"] is False
    assert "al menos dos sesiones" in single["protocols"][0]["message"]
    run_session(env, adult, item)
    both = env.client.get(f"/participants/{adult['id']}/trends", headers=headers(env, env.user_1)).json()
    group = both["protocols"][0]
    assert group["comparable"] is True and len(group["sessions"]) == 2
    assert group["sessions"][0]["sentence"].startswith("En ")


def test_only_the_conductor_and_their_docente_access_and_every_query_is_audited(env):  # noqa: F811
    item, adult = setup(env)
    session_id = run_session(env, adult, item)
    paths = (f"/sessions/{session_id}/timeline", f"/sessions/{session_id}/metrics", f"/participants/{adult['id']}/trends")
    for path in paths:
        for user in (env.user_1, env.docente_a):
            assert env.client.get(path, headers=headers(env, user)).status_code == 200, (path, user.role)
        for user in (env.user_2, env.docente_b, env.admin, env.superadmin):
            assert env.client.get(path, headers=headers(env, user)).status_code == 403, (path, user.role)
    for resource in ("session_timeline", "session_metrics", "participant_trends"):
        results = [entry.result.value for entry in env.audit.query(AuditFilter(resource_type=resource), limit=100)]
        assert results.count("success") == 2 and results.count("denied") == 4, resource
