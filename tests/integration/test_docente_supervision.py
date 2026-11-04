"""El docente supervisa sin estar en cada sesión: «Por revisar» reúne los
reportes enviados y los pedidos de eliminación de su grupo, del más antiguo al
más nuevo. Sus sesiones propias son de demostración y no cuentan en las
estadísticas. Permisos en FastAPI."""
from __future__ import annotations

from tests.integration.test_privacy_accounts import accept_commitment, env, headers  # noqa: F401
from tests.integration.test_session_insights import setup
from tests.integration.test_session_reports import TEXT, call, finished_session


def reviews(env, user):  # noqa: F811
    return env.client.get("/reviews", headers=headers(env, user))


def submitted_report(env):  # noqa: F811
    session_id = finished_session(env)
    report = call(env, "POST", f"/sessions/{session_id}/report", env.user_1).json()
    call(env, "PUT", f"/reports/{report['id']}", env.user_1, {"narrative": TEXT})
    call(env, "POST", f"/reports/{report['id']}/submit", env.user_1)
    return session_id, report["id"]


def test_el_docente_ve_lo_que_su_grupo_envio_a_revision(env):  # noqa: F811
    session_id, report_id = submitted_report(env)
    response = reviews(env, env.docente_a)
    assert response.status_code == 200, response.text
    [item] = response.json()
    assert item["kind"] == "report" and item["session_id"] == session_id and item["report_id"] == report_id
    assert item["user_code"] == env.student_1.student_code and item["session_code"]
    assert env.client.get("/reviews/count", headers=headers(env, env.docente_a)).json() == {"pending": 1}
    # Al aprobarlo deja de esperar.
    call(env, "POST", f"/reports/{report_id}/approve", env.docente_a)
    assert reviews(env, env.docente_a).json() == []


def test_un_pedido_de_eliminacion_espera_al_docente(env):  # noqa: F811
    session_id, _ = submitted_report(env)
    requested = env.client.post(f"/sessions/{session_id}/deletion-request", headers=headers(env, env.user_1))
    assert requested.status_code == 200, requested.text
    kinds = [item["kind"] for item in reviews(env, env.docente_a).json()]
    assert kinds == ["report", "deletion"]  # el reporte llevaba más tiempo esperando


def test_solo_el_docente_del_grupo_lo_ve(env):  # noqa: F811
    submitted_report(env)
    assert reviews(env, env.docente_b).json() == []
    for user in (env.user_1, env.admin, env.superadmin):
        assert reviews(env, user).status_code == 403
        assert env.client.get("/reviews/count", headers=headers(env, user)).status_code == 403


def test_las_sesiones_del_docente_son_de_demostracion(env):  # noqa: F811
    item = setup(env)
    accept_commitment(env, env.docente_a)
    session = env.sessions.start_session(session_type="adulto", owner_user_id=env.docente_a.id,
                                         protocol_id=item["id"], authorization_confirmed=True)
    env.sessions.finish_guided(session.id)
    # No esperan revisión ni cuentan en las estadísticas del docente.
    assert reviews(env, env.docente_a).json() == []
    mine = env.client.get("/statistics?scope=mine", headers=headers(env, env.docente_a))
    assert mine.status_code == 200, mine.text
    assert mine.json()["sessions"]["total"] == 0
