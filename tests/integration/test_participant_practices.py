"""Participantes sin identidad, autorizaciones firmadas, revocación, banco de
estímulos y protocolos versionados (SQLite en memoria, sin servicios externos)."""
from __future__ import annotations

from datetime import timedelta
import zlib

import cv2
import numpy as np
from sqlalchemy import inspect

from emotv.application.ports.privacy_repositories import AuditFilter
from tests.integration.test_privacy_accounts import accept_commitment, env, headers, register  # noqa: F401

SIGNED = "2026-10-20"


def png_bytes(text_chunk: bytes | None = None) -> bytes:
    ok, encoded = cv2.imencode(".png", np.full((8, 8, 3), 120, np.uint8))
    assert ok
    data = encoded.tobytes()
    if text_chunk is None:
        return data
    # Inserta un bloque tEXt (metadatos) justo después de IHDR.
    chunk = b"tEXt" + text_chunk
    block = len(text_chunk).to_bytes(4, "big") + chunk + zlib.crc32(chunk).to_bytes(4, "big")
    return data[:33] + block + data[33:]


def upload_stimulus(env, user, image=None, **fields):  # noqa: F811
    form = {"title": "Paisaje", "kind": "emotional", "category": "Naturaleza", "intensity": "mild", "min_age": "5",
            "origin": "Creación propia del docente", "license": "CC BY 4.0", "expected_expression": "happiness",
            "not_a_participant_photo": "true", **{key: str(value) for key, value in fields.items()}}
    if form["kind"] == "abstract":
        form.pop("expected_expression", None)
    response = env.client.post("/stimuli", headers=headers(env, user), data=form,
                               files={"file": ("estimulo.png", image or png_bytes(), "image/png")})
    assert response.status_code == 201, response.text
    return response.json()


def approve(env, user, stimulus):  # noqa: F811
    response = env.client.post(f"/stimuli/{stimulus['id']}/approve", headers=headers(env, user))
    assert response.status_code == 200, response.text
    return response.json()


def authorize(env, user, participant, *, participation=True, camera=True, child_assent=None):  # noqa: F811
    env.clock.now += timedelta(minutes=1)  # cada formato se registra después del anterior
    body = {"form_version": "F-2026-1", "signed_on": SIGNED, "participation": participation, "camera": camera}
    if child_assent is not None:
        body["child_assent"] = child_assent
    return env.client.post(f"/participants/{participant['id']}/authorizations", headers=headers(env, user), json=body)


def start(env, user, participant, protocol=None):  # noqa: F811
    kind = "participante_infantil" if participant["kind"] == "child" else "participante_adulto"
    body = {"session_type": kind, "participant_id": participant["id"]}
    if protocol is not None:
        body["protocol_id"] = protocol["id"]
    return env.client.post("/sessions", headers=headers(env, user), json=body)


def protocol_body(*stimuli, for_children=False, name="Secuencia", verbal=False):
    return {"name": name, "description": "Exposición breve", "for_children": for_children,
            "steps": [{"stimulus_id": item["id"], "exposure_seconds": 6, "capture_after_seconds": 3,
                       "record_verbal_response": verbal} for item in stimuli]}


def create_protocol(env, user, *stimuli, **options):  # noqa: F811
    response = env.client.post("/protocols", headers=headers(env, user), json=protocol_body(*stimuli, **options))
    assert response.status_code == 201, response.text
    return response.json()


def audit_actions(env, **filters):  # noqa: F811
    return [(item.action.value, item.resource_type, item.result.value)
            for item in env.audit.query(AuditFilter(**filters), limit=500)]


# --- Autorizaciones -----------------------------------------------------------

def test_no_session_without_participation_camera_and_child_assent(env):  # noqa: F811
    adult = register(env, env.user_1)
    assert adult["authorization_status"] == "missing"
    assert start(env, env.user_1, adult).status_code == 409
    assert authorize(env, env.user_1, adult, camera=False).status_code == 201
    assert start(env, env.user_1, adult).status_code == 409  # falta (b)
    assert authorize(env, env.user_1, adult, participation=False).status_code == 201
    assert start(env, env.user_1, adult).status_code == 409  # falta (a)
    assert authorize(env, env.user_1, adult).status_code == 201
    session = start(env, env.user_1, adult)
    assert session.status_code == 201 and session.json()["participant_id"] == adult["id"]

    child = register(env, env.user_1, kind="child")
    assert authorize(env, env.user_1, child).status_code == 422  # el asentimiento es obligatorio con niños
    granted = authorize(env, env.user_1, child, child_assent=False)
    assert granted.status_code == 201 and granted.json()["grantor"] == "guardian"
    assert start(env, env.user_1, child).status_code == 409
    assert authorize(env, env.user_1, child, child_assent=True).status_code == 201
    assert start(env, env.user_1, child).status_code == 201
    # En un adulto no hay asentimiento y lo otorga el propio participante.
    assert authorize(env, env.user_1, adult, child_assent=True).status_code == 422
    assert ("create", "participant_session", "success") in audit_actions(env, resource_type="participant_session")


def test_the_session_type_must_match_the_participant_and_only_the_registrant_conducts(env):  # noqa: F811
    child = register(env, env.user_1, kind="child")
    authorize(env, env.user_1, child, child_assent=True)
    wrong = env.client.post("/sessions", headers=headers(env, env.user_1),
                            json={"session_type": "participante_adulto", "participant_id": child["id"]})
    assert wrong.status_code == 422
    assert env.client.post("/sessions", headers=headers(env, env.user_1),
                           json={"session_type": "participante_adulto"}).status_code == 422
    assert env.client.post("/sessions", headers=headers(env, env.user_1),
                           json={"session_type": "propia", "participant_id": child["id"]}).status_code == 422
    accept_commitment(env, env.docente_a)
    # El docente ve al participante de su grupo, pero no conduce sus sesiones.
    assert start(env, env.docente_a, child).status_code == 403
    accept_commitment(env, env.user_2)
    assert start(env, env.user_2, child).status_code == 403
    denied = [item for item in audit_actions(env, resource_type="participant") if item[2] == "denied"]
    assert len(denied) == 1  # el acceso ajeno queda en la auditoría


def test_revocation_blocks_new_sessions_and_marks_the_participant(env):  # noqa: F811
    child = register(env, env.user_1, kind="child")
    authorization = authorize(env, env.user_1, child, child_assent=True).json()
    assert start(env, env.user_1, child).status_code == 201
    revoked = env.client.post(f"/participants/{child['id']}/authorizations/{authorization['id']}/revoke",
                              headers=headers(env, env.user_1), json={"party": "guardian", "scope": "camera"})
    assert revoked.status_code == 200 and revoked.json()["revoked_scope"] == "camera"
    assert start(env, env.user_1, child).status_code == 409
    # Queda marcado para el docente, que decide su eliminación con el procedimiento de P5.
    seen = {item["id"]: item for item in env.client.get("/participants", headers=headers(env, env.docente_a)).json()}
    assert seen[child["id"]]["authorization_status"] == "revoked"
    assert seen[child["id"]]["authorization_revoked_at"]
    # No se registra una autorización nueva sobre un retiro.
    assert authorize(env, env.user_1, child, child_assent=True).status_code == 409
    assert ("authorization_change", "participant_authorization", "success") in audit_actions(
        env, resource_type="participant_authorization")
    certificate = env.client.post(f"/participants/{child['id']}/delete", headers=headers(env, env.docente_a)).json()
    assert certificate["counts"]["authorizations"] == 1 and certificate["verified"]

    adult = register(env, env.user_1)
    item = authorize(env, env.user_1, adult).json()
    # En un adulto solo retira el propio participante, y no existe asentimiento.
    assert env.client.post(f"/participants/{adult['id']}/authorizations/{item['id']}/revoke",
                           headers=headers(env, env.user_1),
                           json={"party": "guardian", "scope": "participation"}).status_code == 422
    assert env.client.post(f"/participants/{adult['id']}/authorizations/{item['id']}/revoke",
                           headers=headers(env, env.user_2),
                           json={"party": "participant", "scope": "participation"}).status_code == 403


def test_no_identity_data_is_accepted_or_stored(env):  # noqa: F811
    accept_commitment(env, env.user_1)
    base = {"kind": "adult", "age_years": 30}
    for field, value in (("name", "Ana"), ("dni", "12345678"), ("photo", "data:image/png;base64,AA"),
                         ("guardian_name", "Tutor"), ("email", "ana@example.com"), ("code", "P-ELEGIDO")):
        response = env.client.post("/participants", headers=headers(env, env.user_1), json={**base, field: value})
        assert response.status_code == 422, field
    assert env.client.post("/participants", headers=headers(env, env.user_1),
                           json={"kind": "adult", "age_years": 12}).status_code == 422
    assert env.client.post("/participants", headers=headers(env, env.user_1),
                           json={"kind": "child", "age_years": 18}).status_code == 422
    participant = register(env, env.user_1)
    assert participant["code"].startswith("P-") and participant["age_years"] == 30
    assert authorize(env, env.user_1, participant).status_code == 201
    response = env.client.post(f"/participants/{participant['id']}/authorizations", headers=headers(env, env.user_1),
                               json={"form_version": "F", "signed_on": SIGNED, "participation": True,
                                     "camera": True, "signer_name": "Tutor"})
    assert response.status_code == 422
    identity = ("name", "dni", "photo", "foto", "guardian", "tutor", "email", "phone", "telefono", "address", "school")
    for table in ("participants", "participant_authorizations"):
        columns = {column["name"] for column in inspect(env.engine).get_columns(table)}
        assert not [column for column in columns if any(word in column for word in identity)], table
    # El código no se puede editar: no existe ninguna operación para cambiarlo.
    assert env.client.put(f"/participants/{participant['id']}", headers=headers(env, env.user_1),
                          json={"code": "P-OTRO"}).status_code == 405


# --- Banco de estímulos -------------------------------------------------------

def test_users_cannot_create_stimuli_and_see_only_their_group_and_the_institution(env):  # noqa: F811
    for user in (env.user_1, env.superadmin):
        response = env.client.post("/stimuli", headers=headers(env, user),
                                   data={"title": "x", "kind": "emotional", "category": "c", "intensity": "mild",
                                         "min_age": "5", "origin": "o", "license": "l",
                                         "expected_expression": "happiness", "not_a_participant_photo": "true"},
                                   files={"file": ("x.png", png_bytes(), "image/png")})
        assert response.status_code == 403, user.role
    group = upload_stimulus(env, env.docente_a, title="Del grupo A")
    other = upload_stimulus(env, env.docente_b, title="Del grupo B")
    institution = upload_stimulus(env, env.admin, title="Institucional")
    assert (group["scope"], institution["scope"]) == ("group", "institution")
    titles = {item["title"] for item in env.client.get("/stimuli", headers=headers(env, env.user_1)).json()}
    assert titles == {"Del grupo A", "Institucional"}
    assert env.client.get(f"/stimuli/{other['id']}/file", headers=headers(env, env.user_1)).status_code == 404
    # Solo quien lo gestiona lo aprueba: el usuario no, ni otro docente.
    assert env.client.post(f"/stimuli/{group['id']}/approve", headers=headers(env, env.user_1)).status_code == 403
    assert env.client.post(f"/stimuli/{institution['id']}/approve",
                           headers=headers(env, env.docente_a)).status_code == 403
    assert approve(env, env.admin, institution)["approved"]
    assert ("create", "stimulus", "success") in audit_actions(env, resource_type="stimulus")


def test_stimulus_metadata_and_declarations_are_required(env):  # noqa: F811
    base = {"title": "Forma", "kind": "abstract", "category": "Manchas", "intensity": "mild", "min_age": "5",
            "origin": "Creación propia", "license": "Uso docente", "not_a_participant_photo": "true"}

    def post(**changes):
        data = {key: value for key, value in {**base, **changes}.items() if value is not None}
        return env.client.post("/stimuli", headers=headers(env, env.docente_a), data=data,
                               files={"file": ("x.png", png_bytes(), "image/png")})

    assert post().status_code == 422  # falta declarar que no es una lámina proyectiva
    assert post(not_a_participant_photo=None, not_a_projective_test="true").status_code == 422
    assert post(origin=None, not_a_projective_test="true").status_code == 422
    assert post(license=None, not_a_projective_test="true").status_code == 422
    assert post(kind="emotional", not_a_projective_test="true").status_code == 422  # sin expresión esperada
    assert post(expected_expression="happiness", not_a_projective_test="true").status_code == 422
    assert post(not_a_projective_test="true").status_code == 201


def test_stimulus_images_are_validated_and_rewritten_without_metadata(env):  # noqa: F811
    tagged = png_bytes(b"Author\x00Persona real")
    stimulus = upload_stimulus(env, env.docente_a, tagged)
    served = env.client.get(f"/stimuli/{stimulus['id']}/file", headers=headers(env, env.user_1))
    assert served.status_code == 200 and served.headers["content-type"] == "image/png"
    assert b"Persona real" not in served.content and b"tEXt" not in served.content
    response = env.client.post("/stimuli", headers=headers(env, env.docente_a),
                               data={"title": "x", "kind": "emotional", "category": "c", "intensity": "mild",
                                     "min_age": "5", "origin": "o", "license": "l", "expected_expression": "happiness",
                                     "not_a_participant_photo": "true"},
                               files={"file": ("x.png", b"no es una imagen", "image/png")})
    assert response.status_code == 422


def test_moderate_or_older_stimuli_are_not_offered_to_a_child(env):  # noqa: F811
    mild = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Leve"))
    moderate = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Moderado", intensity="moderate"))
    older = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Mayores", min_age=12))
    unapproved = upload_stimulus(env, env.docente_a, title="Sin aprobar")
    offered = {item["title"] for item in env.client.get("/stimuli?child_age=8", headers=headers(env, env.user_1)).json()}
    assert offered == {"Leve"}
    assert {item["title"] for item in env.client.get("/stimuli", headers=headers(env, env.user_1)).json()} == {
        "Leve", "Moderado", "Mayores", "Sin aprobar"}
    # Un protocolo para niños no admite estímulos moderados ni sin aprobar.
    for item in (moderate, unapproved):
        response = env.client.post("/protocols", headers=headers(env, env.user_1),
                                   json=protocol_body(mild, item, for_children=True))
        assert response.status_code == 422, item["title"]
    # Uno aprobado con un estímulo para mayores de 12 no se aplica a un niño de 9.
    protocol = create_protocol(env, env.user_1, mild, older, for_children=True)
    env.client.post(f"/protocols/{protocol['id']}/approve", headers=headers(env, env.docente_a))
    child = register(env, env.user_1, kind="child", age=9)
    authorize(env, env.user_1, child, child_assent=True)
    assert start(env, env.user_1, child, protocol).status_code == 409
    teen = register(env, env.user_1, kind="child", age=13)
    authorize(env, env.user_1, teen, child_assent=True)
    assert start(env, env.user_1, teen, protocol).status_code == 201
    # Retirar un estímulo del banco bloquea los protocolos que lo usan.
    env.client.put(f"/stimuli/{older['id']}/active", headers=headers(env, env.docente_a), json={"active": False})
    assert start(env, env.user_1, teen, protocol).status_code == 409


# --- Protocolos ---------------------------------------------------------------

def test_a_child_protocol_is_used_only_after_the_docente_approves_it(env):  # noqa: F811
    mild = approve(env, env.docente_a, upload_stimulus(env, env.docente_a))
    protocol = create_protocol(env, env.user_1, mild, for_children=True)
    assert not protocol["approved"]
    child = register(env, env.user_1, kind="child")
    authorize(env, env.user_1, child, child_assent=True)
    assert start(env, env.user_1, child, protocol).status_code == 409
    # Ni el propio usuario ni otro docente lo aprueban; el docente de otro grupo ni lo ve.
    assert env.client.post(f"/protocols/{protocol['id']}/approve", headers=headers(env, env.user_1)).status_code == 403
    assert env.client.post(f"/protocols/{protocol['id']}/approve",
                           headers=headers(env, env.docente_b)).status_code == 404
    pending = {item["id"]: item for item in env.client.get("/protocols", headers=headers(env, env.docente_a)).json()}
    assert pending[protocol["id"]]["can_approve"]
    approved = env.client.post(f"/protocols/{protocol['id']}/approve", headers=headers(env, env.docente_a))
    assert approved.status_code == 200 and approved.json()["approved"]
    assert start(env, env.user_1, child, protocol).status_code == 201
    # Con adultos se usa sin aprobación.
    adult_protocol = create_protocol(env, env.user_1, mild)
    adult = register(env, env.user_1)
    authorize(env, env.user_1, adult)
    assert start(env, env.user_1, adult, adult_protocol).status_code == 201
    # Un protocolo para adultos no se aplica a un niño.
    assert start(env, env.user_1, child, adult_protocol).status_code == 409
    assert ("approve", "protocol", "success") in audit_actions(env, resource_type="protocol")


def test_editing_a_used_protocol_creates_a_new_version_that_needs_approval_again(env):  # noqa: F811
    first = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Uno"))
    second = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Dos"))
    protocol = create_protocol(env, env.user_1, first, for_children=True)
    # Sin usar, se edita en el lugar (y pierde la aprobación).
    env.client.post(f"/protocols/{protocol['id']}/approve", headers=headers(env, env.docente_a))
    edited = env.client.put(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1),
                            json=protocol_body(first, second, for_children=True)).json()
    assert edited["id"] == protocol["id"] and edited["version"] == 1 and not edited["approved"]
    env.client.post(f"/protocols/{protocol['id']}/approve", headers=headers(env, env.docente_a))
    child = register(env, env.user_1, kind="child")
    authorize(env, env.user_1, child, child_assent=True)
    session = start(env, env.user_1, child, edited).json()
    assert session["protocol_id"] == protocol["id"]

    renamed = env.client.put(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1),
                             json=protocol_body(second, for_children=True, name="Secuencia corta"))
    assert renamed.status_code == 200
    version = renamed.json()
    assert version["id"] != protocol["id"] and version["family_id"] == protocol["family_id"]
    assert version["version"] == 2 and not version["approved"]
    # La versión usada no cambió y la sesión la conserva.
    old = env.protocols.repository.get(protocol["id"])
    assert old.name == "Secuencia" and len(old.steps) == 2 and old.superseded_at is not None
    assert env.sessions.get_session(session["id"]).protocol_id == protocol["id"]
    assert [item["id"] for item in env.client.get("/protocols", headers=headers(env, env.user_1)).json()] == [version["id"]]
    # La versión anterior ya no se aplica ni se edita; la nueva espera aprobación.
    assert start(env, env.user_1, child, protocol).status_code == 409
    assert env.client.put(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1),
                          json=protocol_body(first)).status_code == 422
    assert start(env, env.user_1, child, version).status_code == 409
    env.client.post(f"/protocols/{version['id']}/approve", headers=headers(env, env.docente_a))
    assert start(env, env.user_1, child, version).status_code == 201


def test_protocol_rules_for_verbal_responses_questionnaires_and_ownership(env):  # noqa: F811
    emotional = upload_stimulus(env, env.docente_a)
    abstract = upload_stimulus(env, env.docente_a, kind="abstract", not_a_projective_test="true", title="Forma")
    # Lo que el participante dice ver solo se registra en imágenes abstractas.
    assert env.client.post("/protocols", headers=headers(env, env.user_1),
                           json=protocol_body(emotional, verbal=True)).status_code == 422
    assert env.client.post("/protocols", headers=headers(env, env.user_1),
                           json=protocol_body(abstract, verbal=True)).status_code == 201
    # Un cuestionario previo inexistente o ajeno no se acepta.
    body = {**protocol_body(abstract), "pre_questionnaire_id": "q-1"}
    assert env.client.post("/protocols", headers=headers(env, env.user_1), json=body).status_code == 422
    # La captura ocurre durante la exposición.
    bad = protocol_body(abstract)
    bad["steps"][0]["capture_after_seconds"] = 9
    assert env.client.post("/protocols", headers=headers(env, env.user_1), json=bad).status_code == 422
    # Un estímulo de otro grupo no se puede usar; el administrador no arma protocolos.
    foreign = upload_stimulus(env, env.docente_b)
    assert env.client.post("/protocols", headers=headers(env, env.user_1),
                           json=protocol_body(foreign)).status_code == 422
    assert env.client.post("/protocols", headers=headers(env, env.admin),
                           json=protocol_body(abstract)).status_code == 403
    mine = create_protocol(env, env.user_1, abstract)
    assert env.client.get(f"/protocols/{mine['id']}", headers=headers(env, env.user_2)).status_code == 404
    assert env.client.put(f"/protocols/{mine['id']}", headers=headers(env, env.docente_a),
                          json=protocol_body(abstract)).status_code == 403
