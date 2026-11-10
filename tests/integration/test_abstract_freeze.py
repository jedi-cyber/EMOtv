"""Imágenes abstractas congeladas (ABSTRACT_STIMULI_ENABLED=false): no se suben,
no se ofrecen ni se aplican en sesiones nuevas, y lo ya registrado se sigue
mostrando. Permisos y reglas en FastAPI."""
from __future__ import annotations

from emotv.domain.guided_session import ABSTRACT_NOTICE
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_protocols_and_stimuli import create_protocol, protocol_body, start, upload_stimulus
from tests.integration.test_session_insights import run_session, setup


def freeze(env):  # noqa: F811
    env.stimuli.abstract_enabled = False


def test_no_se_suben_imagenes_abstractas(env):  # noqa: F811
    freeze(env)
    response = env.client.post("/stimuli", headers=headers(env, env.docente_a), data={
        "title": "Forma", "kind": "abstract", "category": "Manchas", "intensity": "mild", "min_age": "5",
        "origin": "Creación propia", "license": "Uso docente", "not_a_participant_photo": "true",
        "not_a_projective_test": "true"}, files={"file": ("x.png", b"", "image/png")})
    assert response.status_code == 422
    assert "abstractas" in response.json()["detail"]


def test_las_abstractas_existentes_no_se_ofrecen_ni_se_agregan_a_un_protocolo(env):  # noqa: F811
    abstract = upload_stimulus(env, env.docente_a, kind="abstract", not_a_projective_test="true", title="Forma")
    emotional = upload_stimulus(env, env.docente_a)
    freeze(env)
    listed = {item["id"] for item in env.client.get("/stimuli", headers=headers(env, env.docente_a)).json()}
    assert emotional["id"] in listed and abstract["id"] not in listed
    response = env.client.post("/protocols", headers=headers(env, env.user_1),
                               json=protocol_body(emotional, abstract))
    assert response.status_code == 422 and "abstractas" in response.text
    # Lo que la persona dice ver solo se registraba en abstractas: tampoco se acepta.
    assert env.client.post("/protocols", headers=headers(env, env.user_1),
                           json=protocol_body(emotional, verbal=True)).status_code == 422


def test_un_protocolo_con_abstractas_pide_reemplazarlas_y_no_inicia_sesiones(env):  # noqa: F811
    abstract = upload_stimulus(env, env.docente_a, kind="abstract", not_a_projective_test="true", title="Forma")
    emotional = upload_stimulus(env, env.docente_a)
    item = create_protocol(env, env.user_1, emotional, abstract)
    freeze(env)
    listed = {entry["id"]: entry for entry in env.client.get("/protocols", headers=headers(env, env.user_1)).json()}
    assert listed[item["id"]]["needs_image"] is True
    assert start(env, env.user_1, item).status_code != 201


def test_las_sesiones_con_abstractas_se_siguen_mostrando(env):  # noqa: F811
    session_id = run_session(env, setup(env))
    freeze(env)
    metrics = env.client.get(f"/sessions/{session_id}/metrics", headers=headers(env, env.user_1)).json()
    assert metrics["abstract"][0]["said"] == "Una nube"
    assert metrics["abstract_notice"] == ABSTRACT_NOTICE
    timeline = env.client.get(f"/sessions/{session_id}/timeline", headers=headers(env, env.docente_a)).json()
    assert timeline["lanes"]["said"][0]["text"] == "Una nube"
