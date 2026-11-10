"""Plantillas de protocolos: el docente comparte un protocolo suyo con su grupo y
sus usuarios lo copian como protocolo propio. Permisos en FastAPI, copia,
cuestionarios no compartidos y la migración 20261102_34 (SQLite en memoria)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import inspect

from emotv.domain.protocol import Protocol, ProtocolKind
from emotv.infrastructure.persistence.postgres_practice_repositories import PostgresProtocolRepository
from tests.integration.test_practice_persistence import T0, engine, factory  # noqa: F401
from tests.integration.test_practice_persistence import protocol as stored_protocol
from tests.integration.test_privacy_accounts import env, headers  # noqa: F401
from tests.integration.test_questionnaires import create as create_questionnaire
from tests.integration.test_recognition_sessions import recognition, sad_stimulus

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261102_34_protocol_templates.py"


def docente_protocol(env, pre=None, accessible=True):  # noqa: F811
    sad = sad_stimulus(env)
    body = {"name": "Emociones básicas 4 a 6 años", "description": "Reconocer tres emociones", "for_children": True,
            "accessible": accessible, "steps": [{**recognition(sad), "situation": "A Lucía se le cayó su helado."}],
            "pre_questionnaire_id": pre["id"] if pre else None}
    response = env.client.post("/protocols", headers=headers(env, env.docente_a), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def share(env, user, item, shared=True):  # noqa: F811
    return env.client.put(f"/protocols/{item['id']}/share", headers=headers(env, user), json={"shared": shared})


def listed(env, user):  # noqa: F811
    return {item["id"]: item for item in env.client.get("/protocols", headers=headers(env, user)).json()}


def copy(env, user, item):  # noqa: F811
    return env.client.post(f"/protocols/{item['id']}/copy", headers=headers(env, user))


def test_el_grupo_ve_la_plantilla_solo_mientras_esta_compartida(env):  # noqa: F811
    item = docente_protocol(env)
    assert item["shared_with_group"] is False and item["id"] not in listed(env, env.user_1)
    shared = share(env, env.docente_a, item)
    assert shared.status_code == 200 and shared.json()["shared_with_group"] is True
    seen = listed(env, env.user_1)[item["id"]]
    assert seen["owned_by_me"] is False and seen["shared_with_group"] is True
    # Otro grupo no la ve.
    assert item["id"] not in listed(env, env.user_2)
    assert env.client.get(f"/protocols/{item['id']}", headers=headers(env, env.user_2)).status_code == 404
    share(env, env.docente_a, item, shared=False)
    assert item["id"] not in listed(env, env.user_1)


def test_solo_el_docente_autor_comparte(env):  # noqa: F811
    item = docente_protocol(env)
    assert share(env, env.docente_b, item).status_code == 404
    own = env.client.post("/protocols", headers=headers(env, env.user_1), json={
        "name": "Mío", "description": "", "for_children": False, "steps": [recognition(sad_stimulus(env))]}).json()
    # Un usuario no comparte, aunque el protocolo sea suyo; el docente no comparte el de un usuario.
    assert share(env, env.user_1, own).status_code == 403
    assert share(env, env.docente_a, own).status_code == 403


def test_el_usuario_copia_la_plantilla_y_la_copia_es_suya(env):  # noqa: F811
    item = docente_protocol(env)
    share(env, env.docente_a, item)
    response = copy(env, env.user_1, item)
    assert response.status_code == 201, response.text
    copied = response.json()
    assert copied["id"] != item["id"] and copied["owned_by_me"] is True and copied["shared_with_group"] is False
    for field in ("name", "description", "for_children", "accessible", "steps"):
        assert copied[field] == item[field]
    # La plantilla no se edita ni se aplica sin copiarla.
    body = {"name": "Otro", "description": "", "for_children": True, "steps": item["steps"]}
    assert env.client.put(f"/protocols/{item['id']}", headers=headers(env, env.user_1), json=body).status_code == 403


def test_sin_compartir_no_se_copia_y_otro_grupo_tampoco(env):  # noqa: F811
    item = docente_protocol(env)
    assert copy(env, env.user_1, item).status_code == 404
    share(env, env.docente_a, item)
    assert copy(env, env.user_2, item).status_code == 404


def test_el_docente_duplica_un_protocolo_suyo(env):  # noqa: F811
    item = docente_protocol(env)
    response = copy(env, env.docente_a, item)
    assert response.status_code == 201 and response.json()["owned_by_me"] is True


def test_un_cuestionario_que_el_docente_no_comparte_no_se_copia(env):  # noqa: F811
    questionnaire = create_questionnaire(env, env.docente_a)
    item = docente_protocol(env, pre=questionnaire)
    share(env, env.docente_a, item)
    assert copy(env, env.user_1, item).json()["pre_questionnaire_id"] is None
    shared = env.client.put(f"/questionnaires/{questionnaire['id']}/share", headers=headers(env, env.docente_a),
                            json={"shared": True})
    assert shared.status_code == 200
    assert copy(env, env.user_1, item).json()["pre_questionnaire_id"] == questionnaire["id"]


def test_un_examen_no_se_comparte():
    with pytest.raises(ValueError, match="plantilla"):
        Protocol(id="e1", family_id="e1", version=1, owner_user_id="u1", name="Examen", description="",
                 for_children=False, created_at=T0, kind=ProtocolKind.EXAM, shared_with_group=True)


def test_ida_y_vuelta(factory):  # noqa: F811
    item = stored_protocol(shared_with_group=True)
    PostgresProtocolRepository(factory).replace(item)
    assert PostgresProtocolRepository(factory).get("p1") == item


def _run(engine, step: str) -> None:  # noqa: F811
    spec = importlib.util.spec_from_file_location("migration_20261102_34", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (module.revision, module.down_revision) == ("20261102_34", "20261102_33")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()


def test_migracion_downgrade_y_upgrade(engine, factory):  # noqa: F811
    PostgresProtocolRepository(factory).replace(stored_protocol())
    _run(engine, "downgrade")
    assert "shared_with_group" not in {column["name"] for column in inspect(engine).get_columns("protocols")}
    _run(engine, "upgrade")
    assert PostgresProtocolRepository(factory).get("p1").shared_with_group is False
    test_ida_y_vuelta(factory)
