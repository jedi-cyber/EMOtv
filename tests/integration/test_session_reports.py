"""Reporte de sesión: estados, revisión del docente asignado, versiones, cifrado
e impresión auditada (SQLite en memoria, analizador falso)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from emotv.application.ports.privacy_repositories import AuditFilter
from emotv.domain.report import ESTIMATES_NOTICE
from emotv.infrastructure.persistence.models import ReportCommentRecord, SessionReportRecord
from emotv.shared.security.field_encryption import FieldCipher
from tests.integration.test_privacy_accounts import KEY, accept_commitment, env, headers  # noqa: F401
from tests.integration.test_session_insights import run_session, setup

TEXT = "La persona observó las imágenes con atención y pidió una pausa breve."


def finished_session(env):  # noqa: F811
    return run_session(env, setup(env))


def call(env, method, path, user, body=None):  # noqa: F811
    env.clock.now += timedelta(seconds=1)  # cada paso del historial con su propia hora
    return env.client.request(method, path, headers=headers(env, user), json=body)


def test_states_flow_through_the_docente_review(env):  # noqa: F811
    session_id = finished_session(env)
    report = call(env, "POST", f"/sessions/{session_id}/report", env.user_1)
    assert report.status_code == 201, report.text
    report = report.json()
    assert report["status"] == "draft" and report["requires_review"] and report["can_edit"]
    assert call(env, "POST", f"/reports/{report['id']}/submit", env.user_1).status_code == 422  # sin texto
    assert call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": TEXT}).status_code == 200
    submitted = call(env, "POST", f"/reports/{report['id']}/submit", env.user_1).json()
    assert submitted["status"] == "submitted" and not submitted["can_edit"]
    assert call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": "x"}).status_code == 409
    commented = call(env, "POST", f"/reports/{report['id']}/comments", env.docente_a,
                     {"section": "metrics", "text": "Describe también la captura marcada."})
    assert commented.status_code == 201 and commented.json()["comments"][0]["section"] == "metrics"
    returned = call(env, "POST", f"/reports/{report['id']}/return", env.docente_a).json()
    assert returned["status"] == "changes_requested"
    assert call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": TEXT + " Corregido."}).status_code == 200
    call(env, "POST", f"/reports/{report['id']}/submit", env.user_1)
    approved = call(env, "POST", f"/reports/{report['id']}/approve", env.docente_a).json()
    assert approved["status"] == "approved" and approved["approved_at"]
    actions = [item["action"] for item in call(env, "GET", f"/reports/{report['id']}", env.user_1).json()["history"]]
    assert actions == ["created", "edited", "submitted", "commented", "returned", "edited", "submitted", "approved"]


def test_only_the_assigned_docente_reviews(env):  # noqa: F811
    session_id = finished_session(env)
    report = call(env, "POST", f"/sessions/{session_id}/report", env.user_1).json()
    call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": TEXT})
    call(env, "POST", f"/reports/{report['id']}/submit", env.user_1)
    for user in (env.user_1, env.docente_b, env.user_2, env.admin, env.superadmin):
        assert call(env, "POST", f"/reports/{report['id']}/approve", user).status_code == 403, user.role
        assert call(env, "POST", f"/reports/{report['id']}/comments", user,
                    {"section": "general", "text": "x"}).status_code == 403, user.role
    for user in (env.docente_b, env.user_2, env.admin, env.superadmin):
        assert call(env, "GET", f"/reports/{report['id']}", user).status_code == 403, user.role
    assert call(env, "GET", f"/reports/{report['id']}", env.docente_a).json()["can_review"] is True
    assert call(env, "POST", f"/reports/{report['id']}/approve", env.docente_a).status_code == 200
    # Solo quien condujo la sesión crea y redacta su reporte.
    assert call(env, "PUT", f"/reports/{report['id']}", env.docente_a, {"narrative": "x"}).status_code == 403


def test_a_docente_report_needs_no_review(env):  # noqa: F811
    item = setup(env)
    accept_commitment(env, env.docente_a)
    session = env.sessions.start_session(session_type="adulto", owner_user_id=env.docente_a.id,
                                         protocol_id=item["id"], authorization_confirmed=True)
    env.sessions.finish_guided(session.id)
    report = call(env, "POST", f"/sessions/{session.id}/report", env.docente_a).json()
    assert report["requires_review"] is False
    call(env, "PUT", f"/reports/{report['id']}", env.docente_a, {"narrative": TEXT})
    closed = call(env, "POST", f"/reports/{report['id']}/submit", env.docente_a).json()
    assert closed["status"] == "approved" and [entry["action"] for entry in closed["history"]][-1] == "closed"


def test_an_approved_report_is_not_edited_but_versioned(env):  # noqa: F811
    session_id = finished_session(env)
    report = call(env, "POST", f"/sessions/{session_id}/report", env.user_1).json()
    call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": TEXT})
    call(env, "POST", f"/reports/{report['id']}/submit", env.user_1)
    call(env, "POST", f"/reports/{report['id']}/approve", env.docente_a)
    assert call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": "otro"}).status_code == 409
    version = call(env, "POST", f"/reports/{report['id']}/new-version", env.user_1)
    assert version.status_code == 201
    version = version.json()
    assert version["version"] == 2 and version["status"] == "draft" and version["narrative"] == TEXT
    old = call(env, "GET", f"/reports/{report['id']}", env.user_1).json()
    assert old["status"] == "approved" and old["current"] is False and old["narrative"] == TEXT
    assert call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": "otro"}).status_code == 409
    assert call(env, "GET", f"/sessions/{session_id}/report", env.docente_a).json()["id"] == version["id"]
    call(env, "PUT", f"/reports/{version['id']}", env.user_1, {"narrative": TEXT + " Versión 2."})
    # La versión nueva vuelve a revisión.
    assert call(env, "POST", f"/reports/{version['id']}/submit", env.user_1).json()["status"] == "submitted"
    assert call(env, "POST", f"/sessions/{session_id}/report", env.user_1).status_code == 409


def test_texts_are_stored_encrypted(env):  # noqa: F811
    session_id = finished_session(env)
    report = call(env, "POST", f"/sessions/{session_id}/report", env.user_1).json()
    call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": TEXT})
    call(env, "POST", f"/reports/{report['id']}/submit", env.user_1)
    call(env, "POST", f"/reports/{report['id']}/comments", env.docente_a, {"section": "narrative", "text": "Revisa la pausa."})
    with env.factory() as db:
        narrative = db.scalar(select(SessionReportRecord.narrative_encrypted))
        comment = db.scalar(select(ReportCommentRecord.text_encrypted))
    assert "atención" not in narrative and "pausa" not in comment
    assert FieldCipher([KEY]).decrypt(narrative) == TEXT and FieldCipher([KEY]).decrypt(comment) == "Revisa la pausa."


def test_printing_the_approved_report_is_audited(env):  # noqa: F811
    session_id = finished_session(env)
    report = call(env, "POST", f"/sessions/{session_id}/report", env.user_1).json()
    assert report["estimates_notice"] == ESTIMATES_NOTICE and report["abstract_notice"]
    call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": TEXT})
    assert call(env, "POST", f"/reports/{report['id']}/print", env.docente_a).status_code == 409  # sin aprobar
    call(env, "POST", f"/reports/{report['id']}/submit", env.user_1)
    call(env, "POST", f"/reports/{report['id']}/approve", env.docente_a)
    printed = call(env, "POST", f"/reports/{report['id']}/print", env.docente_a)
    assert printed.status_code == 200
    data = printed.json()
    # El código de la sesión aparece en el reporte para cruzarlo con el formato firmado.
    code = env.sessions.get_session(session_id).code
    assert data["session_code"] == code and data["session"]["code"] == code
    assert data["estimates_notice"] == ESTIMATES_NOTICE and "participant_code" not in data
    assert data["session"]["emotion_model_id"] == "hsemotion_enet_b0_8_best_afew"
    assert "comments" not in data and "name" not in str(data.keys())
    assert call(env, "POST", f"/reports/{report['id']}/print", env.user_2).status_code == 403
    prints = [(entry.action.value, entry.result.value) for entry in env.audit.query(
        AuditFilter(resource_type="session_report", action="print"), limit=10)]
    assert prints == [("print", "success")]
    history = call(env, "GET", f"/reports/{report['id']}", env.user_1).json()["history"]
    assert history[-1]["action"] == "printed" and history[-1]["by"] == "docente"


def test_a_report_is_written_only_after_the_session_by_its_conductor(env):  # noqa: F811
    item = setup(env)
    accept_commitment(env, env.user_1)
    running = env.client.post("/sessions", headers=headers(env, env.user_1), json={
        "protocol_id": item["id"], "authorization_confirmed": True}).json()
    assert call(env, "POST", f"/sessions/{running['id']}/report", env.user_1).status_code == 409
    # Una sesión sin protocolo también tiene reporte cuando termina.
    own = env.client.post("/sessions", headers=headers(env, env.user_1),
                          json={"session_type": "propia", "authorization_confirmed": True}).json()
    assert call(env, "POST", f"/sessions/{own['id']}/report", env.user_1).status_code == 409
    env.client.post(f"/sessions/{own['id']}/cancel", headers=headers(env, env.user_1))
    own_report = call(env, "POST", f"/sessions/{own['id']}/report", env.user_1)
    assert own_report.status_code == 201 and own_report.json()["session_code"] == own["code"]
    session_id = run_session(env, item)
    assert call(env, "POST", f"/sessions/{session_id}/report", env.docente_a).status_code == 403
