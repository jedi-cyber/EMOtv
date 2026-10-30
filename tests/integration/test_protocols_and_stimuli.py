"""Inicio de sesiones con protocolo, público del protocolo, sesiones sin
identidad, banco de estímulos y protocolos versionados (SQLite en memoria, sin
servicios externos)."""
from __future__ import annotations

import zlib
from dataclasses import replace

import cv2
import numpy as np
from sqlalchemy import inspect

from emotv.application.commitment_service import load_text
from emotv.application.ports.privacy_repositories import AuditFilter
from tests.integration.test_privacy_accounts import accept_commitment, env, headers  # noqa: F401


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


def start(env, user, protocol=None, session_type=None, confirmed=True):  # noqa: F811
    """Inicia una sesión desde el Analizador: con protocolo o, sin él, con el público elegido."""
    accept_commitment(env, user)
    env.commitments.accept(user, load_text("child_notice").version, "child_notice")
    body = {"authorization_confirmed": confirmed}
    if protocol is not None:
        body["protocol_id"] = protocol["id"]
    if session_type is not None:
        body["session_type"] = session_type
    return env.client.post("/sessions", headers=headers(env, user), json=body)


def protocol_body(*stimuli, for_children=False, name="Secuencia", verbal=False):  # noqa: F811
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


# --- Inicio con protocolo: el público lo define el protocolo ------------------------

def test_with_a_protocol_the_audience_comes_from_the_protocol(env):  # noqa: F811
    mild = approve(env, env.docente_a, upload_stimulus(env, env.docente_a))
    for_adults = create_protocol(env, env.user_1, mild)
    for_children = create_protocol(env, env.user_1, mild, for_children=True, name="Para niños")
    # Con protocolo no se pregunta con quién es la sesión.
    adult = start(env, env.user_1, for_adults)
    assert adult.status_code == 201, adult.text
    assert adult.json()["session_type"] == "adulto" and adult.json()["protocol_id"] == for_adults["id"]
    child = start(env, env.user_1, for_children)
    assert child.status_code == 201 and child.json()["session_type"] == "infantil"
    # El público elegido no contradice el del protocolo; uno para adultos sirve para una sesión propia.
    assert start(env, env.user_1, for_children, "adulto").status_code == 422
    assert start(env, env.user_1, for_adults, "infantil").status_code == 422
    assert start(env, env.user_1, for_adults, "propia").json()["session_type"] == "propia"


def test_a_childrens_protocol_asks_for_the_tutor_and_an_adults_one_for_the_adult(env):  # noqa: F811
    mild = approve(env, env.docente_a, upload_stimulus(env, env.docente_a))
    for_adults = create_protocol(env, env.user_1, mild)
    for_children = create_protocol(env, env.user_1, mild, for_children=True)
    child = start(env, env.user_1, for_children, confirmed=False)
    assert child.status_code == 422 and "tutor autorizó por escrito" in child.json()["detail"]
    adult = start(env, env.user_1, for_adults, confirmed=False)
    assert adult.status_code == 422 and "autorización firmada de la persona adulta" in adult.json()["detail"]
    assert not env.sessions.list_sessions_by_owner(env.user_1.id)


def test_only_the_owner_applies_a_protocol_and_the_docente_does_not_conduct_for_the_user(env):  # noqa: F811
    mild = approve(env, env.docente_a, upload_stimulus(env, env.docente_a))
    protocol = create_protocol(env, env.user_1, mild)
    # El docente ve el protocolo de su grupo, pero no lo aplica; otro usuario ni lo ve.
    assert start(env, env.docente_a, protocol).status_code == 409
    assert start(env, env.user_2, protocol).status_code == 404
    assert start(env, env.user_1, {"id": "no-existe"}).status_code == 404


def test_no_identity_data_is_accepted_or_stored(env):  # noqa: F811
    accept_commitment(env, env.user_1)
    base = {"session_type": "adulto", "authorization_confirmed": True}
    for field, value in (("name", "Ana"), ("dni", "12345678"), ("photo", "data:image/png;base64,AA"),
                         ("guardian_name", "Tutor"), ("email", "ana@example.com"), ("code", "S-ELEGIDO"),
                         ("participant_id", "p-1"), ("age_years", 30)):
        response = env.client.post("/sessions", headers=headers(env, env.user_1), json={**base, field: value})
        assert response.status_code == 422, field
    session = env.client.post("/sessions", headers=headers(env, env.user_1), json=base).json()
    assert session["code"].startswith("S-")
    identity = ("name", "dni", "photo", "foto", "guardian", "tutor", "email", "phone", "telefono", "address",
                "school", "participant", "age")
    for table in ("sessions", "session_deletion_records"):
        columns = {column["name"] for column in inspect(env.engine).get_columns(table)}
        assert not [column for column in columns if any(word in column for word in identity)], table
    assert not {"participants", "participant_authorizations"} & set(inspect(env.engine).get_table_names())
    # El código no se puede editar: no existe ninguna operación para cambiarlo.
    assert env.client.put(f"/sessions/{session['id']}", headers=headers(env, env.user_1),
                          json={"code": "S-OTRO"}).status_code == 405


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


def test_only_mild_and_approved_stimuli_are_offered_for_children(env):  # noqa: F811
    mild = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Leve"))
    moderate = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Moderado", intensity="moderate"))
    older = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Mayores", min_age=12))
    # Las imágenes del docente quedan aprobadas al subirlas; esta es una anterior, sin aprobar.
    unapproved = upload_stimulus(env, env.docente_a, title="Sin aprobar")
    legacy = env.stimuli.repository.get(unapproved["id"])
    env.stimuli.repository.save(replace(legacy, approved_at=None, approved_by_user_id=None))
    # Sin persona registrada no hay edad: no se filtra por edad, solo leves y aprobados.
    offered = {item["title"] for item in
               env.client.get("/stimuli?for_children=true", headers=headers(env, env.user_1)).json()}
    assert offered == {"Leve", "Mayores"}
    assert {item["title"] for item in env.client.get("/stimuli", headers=headers(env, env.user_1)).json()} == {
        "Leve", "Moderado", "Mayores", "Sin aprobar"}
    # Un protocolo para niños no admite estímulos moderados ni sin aprobar.
    for item in (moderate, unapproved):
        response = env.client.post("/protocols", headers=headers(env, env.user_1),
                                   json=protocol_body(mild, item, for_children=True))
        assert response.status_code == 422, item["title"]
        assert "leves y aprobadas" in response.json()["detail"]
    # Sin aprobación del docente: el protocolo se aplica apenas se guarda.
    protocol = create_protocol(env, env.user_1, mild, older, for_children=True)
    assert "approved" not in protocol
    assert env.client.post(f"/protocols/{protocol['id']}/approve", headers=headers(env, env.docente_a)).status_code \
        in (404, 405)
    assert start(env, env.user_1, protocol).status_code == 201
    # Retirar un estímulo del banco bloquea los protocolos que lo usan.
    env.client.put(f"/stimuli/{older['id']}/active", headers=headers(env, env.docente_a), json={"active": False})
    assert start(env, env.user_1, protocol).status_code == 409


# --- Protocolos ---------------------------------------------------------------

def test_the_audience_is_required_when_saving_a_protocol(env):  # noqa: F811
    mild = upload_stimulus(env, env.docente_a)
    body = protocol_body(mild)
    del body["for_children"]
    assert env.client.post("/protocols", headers=headers(env, env.user_1), json=body).status_code == 422
    # Se guarda sin aplicarlo: no crea ninguna sesión.
    saved = create_protocol(env, env.user_1, mild)
    assert saved["for_children"] is False
    assert not env.sessions.list_sessions_by_owner(env.user_1.id)
    assert ("create", "protocol", "success") in audit_actions(env, resource_type="protocol")


def test_editing_a_used_protocol_creates_a_new_version(env):  # noqa: F811
    first = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Uno"))
    second = approve(env, env.docente_a, upload_stimulus(env, env.docente_a, title="Dos"))
    protocol = create_protocol(env, env.user_1, first, for_children=True)
    # Sin usar, se edita en el lugar.
    edited = env.client.put(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1),
                            json=protocol_body(first, second, for_children=True)).json()
    assert edited["id"] == protocol["id"] and edited["version"] == 1
    session = start(env, env.user_1, edited).json()
    assert session["protocol_id"] == protocol["id"]

    renamed = env.client.put(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1),
                             json=protocol_body(second, for_children=True, name="Secuencia corta"))
    assert renamed.status_code == 200
    version = renamed.json()
    assert version["id"] != protocol["id"] and version["family_id"] == protocol["family_id"]
    assert version["version"] == 2
    # La versión usada no cambió y la sesión la conserva.
    old = env.protocols.repository.get(protocol["id"])
    assert old.name == "Secuencia" and len(old.steps) == 2 and old.superseded_at is not None
    assert env.sessions.get_session(session["id"]).protocol_id == protocol["id"]
    assert [item["id"] for item in env.client.get("/protocols", headers=headers(env, env.user_1)).json()] == [version["id"]]
    # La versión anterior ya no se aplica ni se edita; la nueva sí se aplica.
    assert start(env, env.user_1, protocol).status_code == 409
    assert env.client.put(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1),
                          json=protocol_body(first)).status_code == 422
    assert start(env, env.user_1, version).status_code == 201


def test_protocol_rules_for_verbal_responses_questionnaires_and_ownership(env):  # noqa: F811
    emotional = upload_stimulus(env, env.docente_a)
    abstract = upload_stimulus(env, env.docente_a, kind="abstract", not_a_projective_test="true", title="Forma")
    # Lo que la persona dice ver solo se registra en imágenes abstractas.
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
