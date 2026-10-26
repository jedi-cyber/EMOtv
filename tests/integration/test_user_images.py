"""Imágenes propias: detección de personas (detectores falsos, sin pesos ni fotos
de personas reales), revisión del docente, uso en protocolos, vencimiento y
auditoría (SQLite en memoria, sin servicios externos)."""
from __future__ import annotations

from datetime import timedelta

import cv2
import numpy as np
from sqlalchemy import func, select

from emotv.application.ports.privacy_repositories import AuditFilter
from emotv.application.user_image_service import PERSON_REJECTED
from emotv.infrastructure.persistence.models import StimulusRecord
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import (  # noqa: F401
    audit_actions, create_protocol, png_bytes, protocol_body, start, upload_stimulus)


def upload(env, user, *images, audience="children", rights=True, titles=None):  # noqa: F811
    images = images or (png_bytes(),)
    titles = titles or [f"Imagen {index + 1}" for index in range(len(images))]
    return env.client.post(
        "/own-stimuli", headers=headers(env, user),
        data={"titles": titles, "origins": ["Dibujo propio"] * len(images), "audiences": [audience] * len(images),
              "rights_confirmed": ["true" if rights else "false"] * len(images)},
        files=[("files", (f"imagen{index}.png", data, "image/png")) for index, data in enumerate(images)])


def accepted(env, user, *images, **options):  # noqa: F811
    response = upload(env, user, *images, **options)
    assert response.status_code == 201, response.text
    results = response.json()["results"]
    assert all(item["accepted"] for item in results), results
    return [item["image"] for item in results]


def decide(env, user, images, decision, reason=None):  # noqa: F811
    return env.client.post("/own-stimuli/review", headers=headers(env, user),
                           json={"image_ids": [item["id"] for item in images], "decision": decision,
                                 "reason": reason})


def stored_images(env):  # noqa: F811
    with env.factory() as db:
        return db.scalar(select(func.count()).select_from(StimulusRecord).where(StimulusRecord.scope == "user"))


def notices(env, user):  # noqa: F811
    return [item["message"] for item in env.client.get("/notices", headers=headers(env, user)).json()]


# --- Detección de personas ---------------------------------------------------------

def test_a_face_rejects_the_image_and_nothing_is_saved(env):  # noqa: F811
    env.face_confidence = 0.93
    response = upload(env, env.user_1)
    assert response.status_code == 201
    [result] = response.json()["results"]
    assert result == {"title": "Imagen 1", "accepted": False, "message": PERSON_REJECTED, "image": None}
    assert stored_images(env) == 0
    assert ("reject", "user_image", "denied") in audit_actions(env)


def test_a_body_rejects_the_image_and_nothing_is_saved(env):  # noqa: F811
    env.body_confidence = 0.85
    [result] = upload(env, env.user_1).json()["results"]
    assert not result["accepted"] and result["message"] == PERSON_REJECTED
    assert stored_images(env) == 0


def test_in_a_batch_only_the_image_with_a_person_is_rejected(env):  # noqa: F811
    confidences = iter([0.0, 0.95])
    env.images.detect_person = lambda data: next(confidences)
    results = upload(env, env.user_1, png_bytes(), png_bytes()).json()["results"]
    assert [item["accepted"] for item in results] == [True, False]
    assert stored_images(env) == 1


def test_without_detections_the_image_is_pending_rewritten_and_without_metadata(env):  # noqa: F811
    big = cv2.imencode(".png", np.full((1000, 2600, 3), 90, np.uint8))[1].tobytes()
    [image, small] = accepted(env, env.user_1, big, png_bytes(b"Author\x00Ana Perez"))
    assert image["status"] == "pending" and not image["possible_person"] and image["audience"] == "children"
    assert image["expires_at"] is not None and image["batch_id"] == small["batch_id"]
    # La detección vio la imagen reducida a 1280 px por lado.
    assert max(env.detected_shapes[0][:2]) == 1280
    content_type, data = env.stimuli.repository.get_image(small["id"])
    assert content_type == "image/png" and b"Ana Perez" not in data and b"tEXt" not in data
    assert [item["status"] for item in env.client.get("/own-stimuli", headers=headers(env, env.user_1)).json()] == [
        "pending", "pending"]


def test_an_intermediate_confidence_marks_the_image_for_review(env):  # noqa: F811
    env.face_confidence = 0.5
    [image] = accepted(env, env.user_1)
    assert image["possible_person"] is True and image["status"] == "pending"


def test_the_checkbox_the_limit_and_the_role_are_enforced_by_the_server(env):  # noqa: F811
    assert upload(env, env.user_1, rights=False).status_code == 422
    assert upload(env, env.user_1, png_bytes(), png_bytes(), png_bytes(), png_bytes(), png_bytes(), png_bytes(),
                  png_bytes()).status_code == 422  # límite de 6 por usuario
    for staff in (env.docente_a, env.admin, env.superadmin):
        assert upload(env, staff).status_code == 403
    assert stored_images(env) == 0
    # Las imágenes de docentes y del administrador no pasan por revisión.
    assert upload_stimulus(env, env.docente_a)["approved"] is True


# --- Una imagen pendiente no se usa --------------------------------------------------

def test_a_pending_image_cannot_be_chosen_and_only_the_uploader_and_docente_see_it(env):  # noqa: F811
    [image] = accepted(env, env.user_1)
    assert image["id"] not in [item["id"] for item in
                               env.client.get("/stimuli", headers=headers(env, env.user_1)).json()]
    response = env.client.post("/protocols", headers=headers(env, env.user_1), json=protocol_body(image))
    assert response.status_code == 422 and "en revisión" in response.json()["detail"]
    for user, status in ((env.user_1, 200), (env.docente_a, 200), (env.user_2, 404), (env.docente_b, 404),
                         (env.admin, 404), (env.superadmin, 404)):
        assert env.client.get(f"/own-stimuli/{image['id']}/file", headers=headers(env, user)).status_code == status
        assert env.client.get(f"/stimuli/{image['id']}/file", headers=headers(env, user)).status_code == status


def test_the_docente_sees_only_the_batches_of_their_own_users(env):  # noqa: F811
    accepted(env, env.user_1, png_bytes(), png_bytes())
    accepted(env, env.user_2)
    review = env.client.get("/own-stimuli/review", headers=headers(env, env.docente_a)).json()
    assert [(batch["uploaded_by"], len(batch["images"])) for batch in review["pending"]] == [
        ("usuario1@example.com", 2)]
    assert env.client.get("/own-stimuli/review/count", headers=headers(env, env.docente_a)).json() == {"pending": 2}
    assert env.client.get("/own-stimuli/review/count", headers=headers(env, env.docente_b)).json() == {"pending": 1}
    other = env.client.get("/own-stimuli/review", headers=headers(env, env.docente_b)).json()["pending"][0]["images"]
    # Un docente no decide sobre las imágenes de otro grupo; los usuarios y la administración tampoco.
    assert decide(env, env.docente_a, other, "adults").status_code == 404
    for user in (env.user_1, env.admin, env.superadmin):
        assert env.client.get("/own-stimuli/review", headers=headers(env, user)).status_code == 403
        assert decide(env, user, other, "adults").status_code == 403


# --- Revisión: aprobar, reclasificar y eliminar ----------------------------------------

def test_approve_reclassify_and_delete_in_bulk(env):  # noqa: F811
    first, second, third = accepted(env, env.user_1, png_bytes(), png_bytes(), png_bytes())
    # Lo que eligió el usuario («Para niños») se puede cambiar.
    response = decide(env, env.docente_a, [first, second], "adults")
    assert response.status_code == 200
    assert [(item["status"], item["audience"]) for item in response.json()] == [("approved", "adults")] * 2
    assert decide(env, env.docente_a, [second], "children").json()[0]["audience"] == "children"
    assert decide(env, env.docente_a, [third], "delete", "Tiene texto con datos personales").status_code == 200
    assert env.client.get(f"/own-stimuli/{third['id']}/file", headers=headers(env, env.user_1)).status_code == 404
    assert env.stimuli.repository.get(third["id"]) is None  # sin uso: se borra el registro
    assert notices(env, env.user_1) == ["Tu docente eliminó la imagen «Imagen 3». Motivo: Tiene texto con datos "
                                        "personales"]
    # Aprobadas, ya se eligen en los protocolos del usuario.
    offered = {item["id"]: item["audience"]
               for item in env.client.get("/stimuli", headers=headers(env, env.user_1)).json()
               if item["scope"] == "user"}
    assert offered == {first["id"]: "adults", second["id"]: "children"}
    # El docente no usa las imágenes propias de un usuario en sus protocolos.
    response = env.client.post("/protocols", headers=headers(env, env.docente_a), json=protocol_body(second))
    assert response.status_code == 422


def test_an_adults_image_does_not_enter_a_childrens_protocol(env):  # noqa: F811
    for_adults, for_children = accepted(env, env.user_1, png_bytes(), png_bytes())
    decide(env, env.docente_a, [for_adults], "adults")
    decide(env, env.docente_a, [for_children], "children")
    response = env.client.post("/protocols", headers=headers(env, env.user_1),
                               json=protocol_body(for_adults, for_children=True))
    assert response.status_code == 422 and "Para niños" in response.json()["detail"]
    # «Para niños» sirve con niños y con adultos; «Para adultos», solo con adultos.
    assert create_protocol(env, env.user_1, for_children, for_children=True)["needs_image"] is False
    assert create_protocol(env, env.user_1, for_adults, for_children)["needs_image"] is False


def test_deleting_a_used_image_marks_the_protocol_and_notifies_its_owner(env):  # noqa: F811
    [image] = accepted(env, env.user_1)
    decide(env, env.docente_a, [image], "children")
    protocol = create_protocol(env, env.user_1, image, name="Mi secuencia")
    assert start(env, env.user_1, protocol).status_code == 201
    assert decide(env, env.docente_a, [image], "delete").status_code == 200
    # Una sesión la nombra: se borra el archivo y queda solo el registro, sin imagen.
    with env.factory() as db:
        row = db.get(StimulusRecord, image["id"])
        assert bytes(row.image) == b"" and row.deleted_at is not None
    current = env.client.get("/protocols", headers=headers(env, env.user_1)).json()
    assert [item["needs_image"] for item in current] == [True]
    assert any("«Mi secuencia» necesita una imagen" in text for text in notices(env, env.user_1))
    assert start(env, env.user_1, current[0]).status_code == 409


def test_reclassifying_a_used_image_marks_childrens_protocols(env):  # noqa: F811
    [image] = accepted(env, env.user_1)
    decide(env, env.docente_a, [image], "children")
    create_protocol(env, env.user_1, image, for_children=True, name="Para niños")
    create_protocol(env, env.user_1, image, name="Para adultos")
    decide(env, env.docente_a, [image], "adults")
    flags = {item["name"]: item["needs_image"]
             for item in env.client.get("/protocols", headers=headers(env, env.user_1)).json()}
    assert flags == {"Para niños": True, "Para adultos": False}
    assert len([text for text in notices(env, env.user_1) if "necesita una imagen" in text]) == 1


# --- Vencimiento y avisos ------------------------------------------------------------

def test_pending_images_expire_after_a_prior_notice(env):  # noqa: F811
    [image] = accepted(env, env.user_1)
    env.clock.now += timedelta(days=24)
    assert env.images.expire_pending() == 0
    [warning] = notices(env, env.user_1)
    assert "se eliminará el" in warning
    assert env.images.expire_pending() == 0 and len(notices(env, env.user_1)) == 1  # un solo aviso
    env.clock.now += timedelta(days=7)
    assert env.images.expire_pending() == 1
    assert stored_images(env) == 0
    assert "porque no se revisó en 30 días" in notices(env, env.user_1)[-1]
    assert ("retention_purge", "user_image", "success") in audit_actions(env)
    # Un aviso se marca como leído solo por su dueño.
    [first, _] = env.client.get("/notices", headers=headers(env, env.user_1)).json()
    assert env.client.post(f"/notices/{first['id']}/read", headers=headers(env, env.user_2)).status_code == 404
    assert env.client.post(f"/notices/{first['id']}/read", headers=headers(env, env.user_1)).status_code == 204
    assert len(notices(env, env.user_1)) == 1


def test_an_approved_image_does_not_expire(env):  # noqa: F811
    [image] = accepted(env, env.user_1)
    decide(env, env.docente_a, [image], "adults")
    env.clock.now += timedelta(days=60)
    assert env.images.expire_pending() == 0
    assert env.stimuli.repository.get(image["id"]) is not None


# --- Auditoría sin contenido -----------------------------------------------------------

def test_the_audit_records_each_action_without_content(env):  # noqa: F811
    first, second, third = accepted(env, env.user_1, png_bytes(), png_bytes(), png_bytes())
    env.face_confidence = 0.99
    upload(env, env.user_1)
    env.client.get(f"/own-stimuli/{first['id']}/file?preview=true", headers=headers(env, env.docente_a))
    env.client.get(f"/own-stimuli/{first['id']}/file", headers=headers(env, env.user_1))  # miniatura: no es la vista ampliada
    decide(env, env.docente_a, [first], "children")
    decide(env, env.docente_a, [first], "adults")
    decide(env, env.docente_a, [second, third], "delete", "Motivo privado")
    actions = audit_actions(env, resource_type="user_image") + audit_actions(env, resource_type="image_batch")
    assert sorted(actions) == sorted([
        ("view", "user_image", "success"), ("approve", "user_image", "success"),
        ("update", "user_image", "success"), ("delete", "user_image", "success"),
        ("delete", "user_image", "success"), ("reject", "user_image", "denied"),
        ("create", "image_batch", "success"), ("create", "image_batch", "success")])
    stored = repr(env.audit.query(AuditFilter(), limit=500))
    assert "Motivo privado" not in stored and "Dibujo propio" not in stored and "Imagen 1" not in stored


def test_detection_thresholds_and_limits_come_from_the_environment():
    import pytest

    from emotv.config import get_user_image_settings

    settings = get_user_image_settings({"IMAGE_PERSON_REJECT_CONFIDENCE": "0.9", "IMAGE_PERSON_REVIEW_CONFIDENCE": "0.3",
                                        "IMAGE_UPLOAD_LIMIT_PER_USER": "10", "IMAGE_REVIEW_DAYS": "15"})
    assert (settings.person_reject_confidence, settings.person_review_confidence, settings.upload_limit_per_user,
            settings.review_days) == (0.9, 0.3, 10, 15)
    assert get_user_image_settings({}).review_days == 30
    with pytest.raises(ValueError):
        get_user_image_settings({"IMAGE_PERSON_REJECT_CONFIDENCE": "0.3", "IMAGE_PERSON_REVIEW_CONFIDENCE": "0.6"})
    with pytest.raises(ValueError):
        get_user_image_settings({"IMAGE_REVIEW_DAYS": "cero"})
