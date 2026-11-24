"""Eliminar protocolos, cuestionarios e imágenes: solo quien los armó o subió,
las sesiones conservan su registro y lo eliminado deja de listarse (SQLite en
memoria, sin servicios externos)."""
from __future__ import annotations

from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import (
    approve,
    create_protocol,
    start,
    upload_stimulus,
)
from tests.integration.test_questionnaires import create, protocol_with
from tests.integration.test_user_images import accepted


def listed(env, user, path):  # noqa: F811
    response = env.client.get(path, headers=headers(env, user))
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def test_the_owner_deletes_a_protocol_and_its_sessions_keep_it(env):  # noqa: F811
    stimulus = approve(env, env.docente_a, upload_stimulus(env, env.docente_a))
    protocol = create_protocol(env, env.user_1, stimulus)
    session = start(env, env.user_1, protocol)
    assert session.status_code == 201, session.text
    # Solo quien lo armó lo elimina: ni el docente ni otro usuario.
    for other in (env.docente_a, env.user_2):
        assert env.client.delete(f"/protocols/{protocol['id']}", headers=headers(env, other)).status_code in (403, 404)
    assert env.client.delete(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1)).status_code == 204
    assert protocol["id"] not in listed(env, env.user_1, "/protocols")
    assert env.client.get(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1)).status_code == 404
    assert start(env, env.user_1, protocol).status_code == 404
    # La sesión que lo usó sigue ahí, con su protocolo.
    kept = env.client.get(f"/sessions/{session.json()['id']}", headers=headers(env, env.user_1))
    assert kept.status_code == 200 and kept.json()["protocol_id"] == protocol["id"]
    assert env.client.delete(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1)).status_code == 404


def test_a_questionnaire_in_use_asks_to_remove_it_from_the_protocol_first(env):  # noqa: F811
    questionnaire = create(env, env.user_1)
    protocol = protocol_with(env, env.user_1, questionnaire)
    path = f"/questionnaires/{questionnaire['id']}"
    assert env.client.delete(path, headers=headers(env, env.user_2)).status_code in (403, 404)
    blocked = env.client.delete(path, headers=headers(env, env.user_1))
    assert blocked.status_code == 422 and f"«{protocol['name']}»" in blocked.json()["detail"]
    # Al eliminar el protocolo, el cuestionario ya se puede eliminar.
    assert env.client.delete(f"/protocols/{protocol['id']}", headers=headers(env, env.user_1)).status_code == 204
    assert env.client.delete(path, headers=headers(env, env.user_1)).status_code == 204
    assert questionnaire["id"] not in listed(env, env.user_1, "/questionnaires")
    assert env.client.get(path, headers=headers(env, env.user_1)).status_code == 404


def test_an_unused_questionnaire_is_deleted(env):  # noqa: F811
    questionnaire = create(env, env.user_1, title="Sin usar")
    assert env.client.delete(f"/questionnaires/{questionnaire['id']}",
                             headers=headers(env, env.user_1)).status_code == 204
    assert questionnaire["id"] not in listed(env, env.user_1, "/questionnaires")


def test_the_uploader_deletes_their_own_image(env):  # noqa: F811
    image = accepted(env, env.user_1)[0]
    path = f"/own-stimuli/{image['id']}"
    assert env.client.delete(path, headers=headers(env, env.user_2)).status_code in (403, 404)
    assert env.client.delete(path, headers=headers(env, env.user_1)).status_code == 204
    assert env.client.get(f"{path}/file", headers=headers(env, env.user_1)).status_code == 404


def test_the_docente_deletes_a_stimulus_they_manage(env):  # noqa: F811
    stimulus = approve(env, env.docente_a, upload_stimulus(env, env.docente_a))
    path = f"/stimuli/{stimulus['id']}"
    assert env.client.delete(path, headers=headers(env, env.user_1)).status_code in (403, 404)
    assert env.client.delete(path, headers=headers(env, env.docente_a)).status_code == 204
    assert stimulus["id"] not in listed(env, env.docente_a, "/stimuli")
