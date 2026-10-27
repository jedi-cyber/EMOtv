"""Examen simulado: rutas del docente (SQLite en memoria, sin modelos ni cámaras).

Las estaciones se unen en el Bloque 3; aquí se simulan guardando la sesión de
cada una directamente.
"""
from __future__ import annotations

from datetime import timedelta
from itertools import count

from emotv.domain.session import EmotionalSession
from emotv.domain.session_state import SessionState
from tests.integration.test_privacy_accounts import accept_commitment, audit_actions, env, headers  # noqa: F401

_codes = count(1)


def create_exam(env, user):  # noqa: F811
    accept_commitment(env, user)
    response = env.client.post("/exams", headers=headers(env, user))
    assert response.status_code == 201, response.text
    return response.json()


def join(env, exam, state=SessionState.CREATED):  # noqa: F811
    """Una estación que se une al examen: su sesión, sin consentimiento confirmado."""
    env.clock.now += timedelta(seconds=1)
    return env.sessions.repository.save(EmotionalSession(
        id=f"estacion-{next(_codes)}", started_at=env.clock.now, state=state, session_type="adulto",
        completed_at=env.clock.now if state is SessionState.CANCELLED else None,
        owner_user_id=exam["owner"], protocol_id=env.exams.repository.get(exam["id"]).protocol_id,
        code=f"S-EST{next(_codes):03d}", exam_id=exam["id"]))


def post(env, user, path):  # noqa: F811
    return env.client.post(path, headers=headers(env, user))


def test_crear_examen_es_un_clic(env):  # noqa: F811
    exam = create_exam(env, env.docente_a)
    assert exam["state"] == "open" and len(exam["join_code"]) == 6
    assert exam["stations"] == [] and exam["station_count"] == 0 and exam["waiting_consent"] == 0
    # El protocolo «Examen simulado» se crea solo y se reutiliza en el siguiente examen.
    second = create_exam(env, env.docente_a)
    assert second["join_code"] != exam["join_code"]
    first_protocol = env.exams.repository.get(exam["id"]).protocol_id
    assert env.exams.repository.get(second["id"]).protocol_id == first_protocol
    listed = env.client.get("/exams", headers=headers(env, env.docente_a)).json()
    assert {item["id"] for item in listed} == {exam["id"], second["id"]}


def test_solo_un_docente_crea_y_ve_sus_examenes(env):  # noqa: F811
    for user in (env.user_1, env.admin, env.superadmin):
        assert post(env, user, "/exams").status_code == 403
        assert env.client.get("/exams", headers=headers(env, user)).status_code == 403
    exam = create_exam(env, env.docente_a)
    # Otro docente no ve ni conduce un examen ajeno.
    for path in ("", "/consents", "/start", "/finish"):
        method = env.client.get if path == "" else env.client.post
        assert method(f"/exams/{exam['id']}{path}", headers=headers(env, env.docente_b)).status_code == 404
    assert env.client.get("/exams", headers=headers(env, env.docente_b)).json() == []


def test_sin_compromiso_de_confidencialidad_no_hay_examen(env):  # noqa: F811
    response = post(env, env.docente_a, "/exams")
    assert response.status_code == 428


def test_un_boton_confirma_los_consentimientos_de_las_estaciones_unidas(env):  # noqa: F811
    exam = create_exam(env, env.docente_a)
    exam["owner"] = env.docente_a.id
    first, second = join(env, exam), join(env, exam)
    detail = env.client.get(f"/exams/{exam['id']}", headers=headers(env, env.docente_a)).json()
    assert detail["waiting_consent"] == 2
    assert [item["code"] for item in detail["stations"]] == [first.code, second.code]

    confirmed = post(env, env.docente_a, f"/exams/{exam['id']}/consents")
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["confirmed"] == 2 and body["waiting_consent"] == 0 and body["consent_confirmed_at"]
    assert all(item["consent_confirmed"] for item in body["stations"])
    # El consentimiento queda en cada sesión.
    assert env.sessions.get_session(first.id).authorization_confirmed_at is not None

    # Una estación que se une después espera una nueva confirmación.
    late = join(env, exam)
    detail = env.client.get(f"/exams/{exam['id']}", headers=headers(env, env.docente_a)).json()
    assert detail["waiting_consent"] == 1
    assert [item["consent_confirmed"] for item in detail["stations"]] == [True, True, False]
    assert post(env, env.docente_a, f"/exams/{exam['id']}/consents").json()["confirmed"] == 1
    assert env.sessions.get_session(late.id).authorization_confirmed_at is not None
    # Sin estaciones pendientes no hay nada que confirmar.
    assert post(env, env.docente_a, f"/exams/{exam['id']}/consents").status_code == 409


def test_una_estacion_terminada_no_se_confirma(env):  # noqa: F811
    exam = create_exam(env, env.docente_a)
    exam["owner"] = env.docente_a.id
    join(env, exam, state=SessionState.CANCELLED)
    assert post(env, env.docente_a, f"/exams/{exam['id']}/consents").status_code == 409


def test_iniciar_y_terminar(env):  # noqa: F811
    exam = create_exam(env, env.docente_a)
    exam["owner"] = env.docente_a.id
    # Sin estaciones con consentimiento no se inicia.
    assert post(env, env.docente_a, f"/exams/{exam['id']}/start").status_code == 409
    join(env, exam)
    assert post(env, env.docente_a, f"/exams/{exam['id']}/start").status_code == 409
    post(env, env.docente_a, f"/exams/{exam['id']}/consents")
    started = post(env, env.docente_a, f"/exams/{exam['id']}/start")
    assert started.status_code == 200 and started.json()["state"] == "in_progress"
    assert started.json()["started_at"]
    assert post(env, env.docente_a, f"/exams/{exam['id']}/start").status_code == 409
    # Mientras no termina, se pueden unir y confirmar estaciones nuevas.
    join(env, exam)
    assert post(env, env.docente_a, f"/exams/{exam['id']}/consents").json()["confirmed"] == 1
    closed = post(env, env.docente_a, f"/exams/{exam['id']}/finish")
    assert closed.status_code == 200 and closed.json()["state"] == "closed" and closed.json()["closed_at"]
    for path in ("/start", "/finish"):
        assert post(env, env.docente_a, f"/exams/{exam['id']}{path}").status_code == 409
    join(env, exam)
    assert post(env, env.docente_a, f"/exams/{exam['id']}/consents").status_code == 409


def test_un_examen_sin_iniciar_tambien_se_termina(env):  # noqa: F811
    exam = create_exam(env, env.docente_a)
    closed = post(env, env.docente_a, f"/exams/{exam['id']}/finish")
    assert closed.status_code == 200 and closed.json()["state"] == "closed"
    assert closed.json()["started_at"] is None


def test_el_docente_ve_estados_nunca_expresiones(env):  # noqa: F811
    exam = create_exam(env, env.docente_a)
    exam["owner"] = env.docente_a.id
    join(env, exam)
    station = env.client.get(f"/exams/{exam['id']}", headers=headers(env, env.docente_a)).json()["stations"][0]
    assert set(station) == {"code", "joined_at", "consent_confirmed", "finished"}


def test_el_protocolo_de_examen_no_se_usa_en_practicas(env):  # noqa: F811
    exam = create_exam(env, env.docente_a)
    protocol_id = env.exams.repository.get(exam["id"]).protocol_id
    auth = headers(env, env.docente_a)
    assert env.client.get("/protocols", headers=auth).json() == []
    assert env.client.get(f"/protocols/{protocol_id}", headers=auth).status_code == 404
    edit = env.client.put(f"/protocols/{protocol_id}", headers=auth,
                          json={"name": "Otro", "description": "", "for_children": False, "steps": []})
    assert edit.status_code in (404, 422)
    started = env.client.post("/sessions", headers=auth,
                              json={"protocol_id": protocol_id, "authorization_confirmed": True})
    assert started.status_code == 404


def test_pasos_del_docente_quedan_auditados_sin_contenido(env):  # noqa: F811
    exam = create_exam(env, env.docente_a)
    exam["owner"] = env.docente_a.id
    join(env, exam)
    post(env, env.docente_a, f"/exams/{exam['id']}/consents")
    post(env, env.docente_a, f"/exams/{exam['id']}/start")
    post(env, env.docente_a, f"/exams/{exam['id']}/finish")
    # El reloj de prueba está fijo: se comparan las acciones sin depender del orden.
    actions = sorted(item for item in audit_actions(env) if item[1] == "exam")
    assert actions == [("authorization_change", "exam", "success"), ("create", "exam", "success"),
                       ("update", "exam", "success"), ("update", "exam", "success")]
