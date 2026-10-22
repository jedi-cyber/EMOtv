"""Cuestionarios creados por quien conduce la sesión: versiones, plantillas,
aplicación antes del analizador y respuestas cifradas (SQLite en memoria)."""
from __future__ import annotations

import json
import re

import pytest
from sqlalchemy import select

from emotv.application.ports.privacy_repositories import AuditFilter
from emotv.infrastructure.persistence.models import QuestionnaireResponseRecord
from emotv.shared.security.field_encryption import FieldCipher, FieldEncryptionError
from tests.integration.test_participant_practices import (
    approve,
    authorize,
    create_protocol,
    protocol_body,
    upload_stimulus,
)
from tests.integration.test_privacy_accounts import KEY, accept_commitment, env, headers, register  # noqa: F401

SCORE_WORDS = re.compile(r"(score|puntaje|puntuaci|total|suma|promedio|average|interpret|diagn|resultado|nivel)", re.I)


def questions():
    return [
        {"id": "animo", "kind": "faces", "text": "¿Cómo te sientes?", "required": True},
        {"id": "energia", "kind": "scale", "text": "¿Cuánta energía tienes?", "required": True, "scale_points": 5,
         "min_label": "Poca", "max_label": "Mucha"},
        {"id": "lugar", "kind": "single_choice", "text": "¿Dónde estás?", "options": ["Casa", "Aula"]},
        {"id": "apoyos", "kind": "multiple_choice", "text": "¿Qué te ayuda?", "options": ["Música", "Caminar", "Hablar"]},
        {"id": "nota", "kind": "short_text", "text": "¿Algo más?"},
    ]


def create(env, user, title="Antes de empezar", items=None):  # noqa: F811
    response = env.client.post("/questionnaires", headers=headers(env, user),
                               json={"title": title, "instructions": "Responde con calma.",
                                     "questions": items or questions()})
    assert response.status_code == 201, response.text
    return response.json()


def own_session(env, user, questionnaire=None):  # noqa: F811
    accept_commitment(env, user)
    body = {"session_type": "propia"}
    if questionnaire is not None:
        body["pre_questionnaire_id"] = questionnaire["id"]
    response = env.client.post("/sessions", headers=headers(env, user), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def answer(env, user, session, answers, moment="pre", entry_mode="participant"):  # noqa: F811
    return env.client.post(f"/sessions/{session['id']}/questionnaires/{moment}", headers=headers(env, user),
                           json={"answers": answers, "entry_mode": entry_mode})


FULL = {"animo": 2, "energia": 4, "lugar": "Aula", "apoyos": ["Hablar", "Música"], "nota": "Dormí poco"}
# Tal como se dieron; la opción múltiple conserva el orden de sus opciones.
STORED = {**FULL, "apoyos": ["Música", "Hablar"]}


def first_socket_message(env, user, session):  # noqa: F811
    with env.client.websocket_connect("/ws/activity") as socket:
        socket.send_json({"type": "authenticate", "token": env.auth.create_access_token(user),
                          "session_id": session["id"]})
        return socket.receive_json()


def strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


# --- Aplicación antes del analizador ------------------------------------------

def test_the_pre_questionnaire_is_answered_before_calibration(env):  # noqa: F811
    questionnaire = create(env, env.user_1)
    session = own_session(env, env.user_1, questionnaire)
    assert session["pre_questionnaire_id"] == questionnaire["id"]
    blocked = first_socket_message(env, env.user_1, session)
    assert blocked["type"] == "error" and blocked["code"] == 4428
    pending = env.client.get(f"/sessions/{session['id']}/questionnaires/pre", headers=headers(env, env.user_1)).json()
    assert pending["answered"] is False and pending["questionnaire"]["id"] == questionnaire["id"]
    assert answer(env, env.user_1, session, FULL).status_code == 201
    # Ya no lo bloquea el cuestionario (el analizador de prueba no tiene modelo cargado).
    after = first_socket_message(env, env.user_1, session)
    assert after.get("code") != 4428


def test_an_own_session_can_skip_the_questionnaire(env):  # noqa: F811
    session = own_session(env, env.user_1)
    assert session["pre_questionnaire_id"] is None
    assert first_socket_message(env, env.user_1, session).get("code") != 4428
    assert env.client.get(f"/sessions/{session['id']}/questionnaires/pre",
                          headers=headers(env, env.user_1)).status_code == 409


def test_required_questions_and_answer_types_are_enforced(env):  # noqa: F811
    questionnaire = create(env, env.user_1)
    session = own_session(env, env.user_1, questionnaire)
    assert answer(env, env.user_1, session, {"energia": 3}).status_code == 422  # falta «¿Cómo te sientes?»
    for wrong in ({"animo": 6}, {"energia": 0}, {"lugar": "Parque"}, {"apoyos": ["Dormir"]}, {"nota": "x" * 501},
                  {"otra": 1}):
        assert answer(env, env.user_1, session, {**FULL, **wrong}).status_code == 422, wrong
    # Solo las obligatorias bastan; las demás pueden quedar vacías.
    assert answer(env, env.user_1, session, {"animo": 3, "energia": 1, "nota": "  "}).status_code == 201
    assert answer(env, env.user_1, session, FULL).status_code == 409  # ya se respondió
    # Solo quien conduce la sesión registra respuestas.
    other = own_session(env, env.user_1, questionnaire)
    assert answer(env, env.docente_a, other, FULL).status_code == 403


def test_question_definitions_are_validated(env):  # noqa: F811
    accept_commitment(env, env.user_1)

    def post(item):
        return env.client.post("/questionnaires", headers=headers(env, env.user_1),
                               json={"title": "T", "questions": [item]})

    assert post({"id": "a", "kind": "scale", "text": "E", "scale_points": 8, "min_label": "a", "max_label": "b"}).status_code == 422
    assert post({"id": "a", "kind": "scale", "text": "E", "scale_points": 1, "min_label": "a", "max_label": "b"}).status_code == 422
    assert post({"id": "a", "kind": "scale", "text": "E", "scale_points": 4}).status_code == 422  # sin extremos
    assert post({"id": "a", "kind": "single_choice", "text": "E", "options": ["Sí"]}).status_code == 422
    assert post({"id": "a", "kind": "short_text", "text": "E", "options": ["x", "y"]}).status_code == 422
    assert post({"id": "a", "kind": "scale", "text": "E", "scale_points": 2, "min_label": "No", "max_label": "Sí"}).status_code == 201
    assert env.client.post("/questionnaires", headers=headers(env, env.admin),
                           json={"title": "T", "questions": questions()}).status_code == 403


# --- Versiones y plantillas -----------------------------------------------------

def test_a_used_questionnaire_creates_a_new_version(env):  # noqa: F811
    questionnaire = create(env, env.user_1)
    renamed = env.client.put(f"/questionnaires/{questionnaire['id']}", headers=headers(env, env.user_1),
                             json={"title": "Al llegar", "questions": questions()}).json()
    assert renamed["id"] == questionnaire["id"] and renamed["version"] == 1  # sin usar: se edita
    session = own_session(env, env.user_1, questionnaire)
    answer(env, env.user_1, session, FULL)
    edited = env.client.put(f"/questionnaires/{questionnaire['id']}", headers=headers(env, env.user_1),
                            json={"title": "Al llegar (corto)", "questions": questions()[:1]})
    assert edited.status_code == 200
    version = edited.json()
    assert version["id"] != questionnaire["id"] and version["family_id"] == questionnaire["family_id"]
    assert version["version"] == 2 and not version["used"]
    old = env.questionnaires.repository.get(questionnaire["id"])
    assert old.title == "Al llegar" and len(old.questions) == 5 and not old.current
    # La sesión conserva la versión exacta que se respondió.
    responses = env.client.get(f"/sessions/{session['id']}/questionnaire-responses", headers=headers(env, env.user_1)).json()
    assert responses[0]["questionnaire"]["id"] == questionnaire["id"]
    assert len(responses[0]["questionnaire"]["questions"]) == 5
    # Una sesión nueva aplica la versión vigente aunque se indique la anterior.
    newer = own_session(env, env.user_1, questionnaire)
    assert newer["pre_questionnaire_id"] == version["id"]
    assert [item["id"] for item in env.client.get("/questionnaires", headers=headers(env, env.user_1)).json()] == [version["id"]]
    assert env.client.put(f"/questionnaires/{questionnaire['id']}", headers=headers(env, env.user_1),
                          json={"title": "x", "questions": questions()}).status_code == 422


def test_starter_template_and_docente_templates_shared_with_the_group(env):  # noqa: F811
    starter = env.client.post("/questionnaires/starter", headers=headers(env, env.user_1))
    assert starter.status_code == 201
    texts = [(item["kind"], item["text"]) for item in starter.json()["questions"]]
    assert texts == [("faces", "¿Cómo te sientes?"), ("faces", "¿Qué tan tranquilo o inquieto estás?")]
    # Es una copia propia y editable.
    assert env.client.put(f"/questionnaires/{starter.json()['id']}", headers=headers(env, env.user_1),
                          json={"title": "Mi versión", "questions": questions()}).status_code == 200

    template = create(env, env.docente_a, title="Plantilla del grupo")
    assert env.client.put(f"/questionnaires/{template['id']}/share", headers=headers(env, env.user_1),
                          json={"shared": True}).status_code == 403
    shared = env.client.put(f"/questionnaires/{template['id']}/share", headers=headers(env, env.docente_a),
                            json={"shared": True})
    assert shared.status_code == 200 and shared.json()["shared_with_group"]
    seen = {item["title"]: item for item in env.client.get("/questionnaires", headers=headers(env, env.user_1)).json()}
    assert "Plantilla del grupo" in seen and not seen["Plantilla del grupo"]["owned_by_me"]
    others = {item["title"] for item in env.client.get("/questionnaires", headers=headers(env, env.user_2)).json()}
    assert "Plantilla del grupo" not in others
    assert env.client.get(f"/questionnaires/{template['id']}", headers=headers(env, env.user_2)).status_code == 404
    # El usuario no edita la plantilla: la copia y modifica su copia.
    assert env.client.put(f"/questionnaires/{template['id']}", headers=headers(env, env.user_1),
                          json={"title": "x", "questions": questions()}).status_code == 403
    copy = env.client.post(f"/questionnaires/{template['id']}/copy", headers=headers(env, env.user_1))
    assert copy.status_code == 201 and copy.json()["owned_by_me"] and copy.json()["family_id"] != template["family_id"]
    assert env.client.put(f"/questionnaires/{copy.json()['id']}", headers=headers(env, env.user_1),
                          json={"title": "Copia modificada", "questions": questions()[:2]}).status_code == 200


# --- Protocolos y participantes -------------------------------------------------

def test_a_protocol_indicates_pre_and_post_questionnaires_for_a_participant(env):  # noqa: F811
    stimulus = approve(env, env.docente_a, upload_stimulus(env, env.docente_a))
    pre, post = create(env, env.user_1, "Previo"), create(env, env.user_1, "Posterior", questions()[2:])
    protocol = env.client.post("/protocols", headers=headers(env, env.user_1),
                               json={**protocol_body(stimulus), "pre_questionnaire_id": pre["id"],
                                     "post_questionnaire_id": post["id"]})
    assert protocol.status_code == 201, protocol.text
    participant = register(env, env.user_1)
    authorize(env, env.user_1, participant)
    session = env.client.post("/sessions", headers=headers(env, env.user_1),
                              json={"session_type": "participante_adulto", "participant_id": participant["id"],
                                    "protocol_id": protocol.json()["id"]}).json()
    assert (session["pre_questionnaire_id"], session["post_questionnaire_id"]) == (pre["id"], post["id"])
    # Con protocolo no se eligen otros cuestionarios.
    assert env.client.post("/sessions", headers=headers(env, env.user_1),
                           json={"session_type": "participante_adulto", "participant_id": participant["id"],
                                 "protocol_id": protocol.json()["id"], "pre_questionnaire_id": post["id"]}).status_code == 422
    assert first_socket_message(env, env.user_1, session)["code"] == 4428
    assert answer(env, env.user_1, session, FULL, entry_mode="participant").status_code == 201
    # El posterior es opcional en sus preguntas y lo puede registrar a mano quien conduce.
    assert answer(env, env.user_1, session, {}, moment="post", entry_mode="conductor").status_code == 201
    listed = env.client.get(f"/sessions/{session['id']}/questionnaire-responses", headers=headers(env, env.docente_a)).json()
    assert [(item["moment"], item["entry_mode"]) for item in listed] == [("pre", "participant"), ("post", "conductor")]
    # La eliminación del participante incluye sus respuestas.
    certificate = env.client.post(f"/participants/{participant['id']}/delete", headers=headers(env, env.docente_a)).json()
    assert certificate["counts"]["questionnaire_responses"] == 2 and certificate["verified"]


# --- Cifrado, acceso y ausencia de puntajes -------------------------------------

def test_answers_are_stored_encrypted(env):  # noqa: F811
    questionnaire = create(env, env.user_1)
    session = own_session(env, env.user_1, questionnaire)
    answer(env, env.user_1, session, FULL)
    with env.factory() as db:
        stored = db.scalar(select(QuestionnaireResponseRecord.answers_encrypted))
    assert "Dormí poco" not in stored and "Aula" not in stored and "energia" not in stored
    with pytest.raises(FieldEncryptionError):
        from cryptography.fernet import Fernet
        FieldCipher([Fernet.generate_key().decode()]).decrypt(stored)
    assert json.loads(FieldCipher([KEY]).decrypt(stored)) == STORED


def test_only_the_conductor_and_their_docente_see_the_answers_and_every_query_is_audited(env):  # noqa: F811
    questionnaire = create(env, env.user_1)
    session = own_session(env, env.user_1, questionnaire)
    answer(env, env.user_1, session, FULL)
    path = f"/sessions/{session['id']}/questionnaire-responses"
    for user in (env.user_1, env.docente_a):
        response = env.client.get(path, headers=headers(env, user))
        assert response.status_code == 200 and response.json()[0]["answers"] == STORED, user.role
    for user in (env.user_2, env.docente_b, env.admin, env.superadmin):
        assert env.client.get(path, headers=headers(env, user)).status_code == 403, user.role
    entries = [(item.action.value, item.result.value)
               for item in env.audit.query(AuditFilter(resource_type="questionnaire_response"), limit=100)]
    assert entries.count(("view", "success")) == 2 and entries.count(("view", "denied")) == 4
    assert ("create", "success") in entries


def test_no_score_or_interpretation_is_ever_returned(env):  # noqa: F811
    questionnaire = create(env, env.user_1)
    session = own_session(env, env.user_1, questionnaire)
    submitted = answer(env, env.user_1, session, FULL)
    assert set(submitted.json()) == {"id", "moment"}
    listed = env.client.get(f"/sessions/{session['id']}/questionnaire-responses", headers=headers(env, env.user_1)).json()
    assert set(listed[0]) == {"id", "moment", "entry_mode", "submitted_at", "questionnaire", "answers"}
    # Las respuestas vuelven tal como se dieron (el orden de la opción múltiple sigue al de las opciones).
    assert listed[0]["answers"] == STORED
    keys = {key for item in listed for key in item} | set(listed[0]["questionnaire"]) | set(listed[0]["answers"])
    assert not [key for key in keys if SCORE_WORDS.search(key)]
    for path in ("/questionnaires", f"/questionnaires/{questionnaire['id']}"):
        assert not [text for text in strings(env.client.get(path, headers=headers(env, env.user_1)).json())
                    if SCORE_WORDS.search(text)], path
