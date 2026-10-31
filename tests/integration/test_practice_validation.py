"""Validación de los modelos con adultos voluntarios: protocolo de ejemplo (solo
demo y cuentas PRUEBA-NN) y exportación CSV agregada para administración
(SQLite en memoria; sin imágenes, modelos ni archivos de resultados)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from emotv.application.practice_validation_service import (
    CSV_HEADER,
    VALIDATION_PROTOCOL_NAME,
    VALIDATION_TARGETS,
    PracticeValidationService,
    validation_rows,
)
from emotv.domain.guided_session import PracticeResult
from emotv.infrastructure.persistence.models import UserRecord
from emotv.interfaces.web.practice_validation_router import create_practice_validation_router
from tests.integration.test_guided_sessions import guided
from tests.integration.test_practice_statistics import protocol as practice_protocol
from tests.integration.test_privacy_accounts import accept_commitment, audit_actions, env, headers  # noqa: F401
from tests.integration.test_session_statistics import session


def volunteer(env, user):  # noqa: F811
    with env.factory.begin() as db:
        db.execute(update(UserRecord).where(UserRecord.id == user.id).values(is_test_account=True))


def build(env, mode="demo"):  # noqa: F811
    service = PracticeValidationService(
        env.protocols.repository, env.sessions, env.guided.repository, env.audit, mode,
        env.users.is_test_account, env.users.list_test_account_ids, clock=lambda: env.clock.now)
    env.protocols.validation_usable = service.usable
    app = FastAPI()
    app.include_router(create_practice_validation_router(service, env.auth, env.users))
    return SimpleNamespace(service=service, client=TestClient(app))


@pytest.fixture
def validation(env):  # noqa: F811
    volunteer(env, env.user_1)
    return build(env)


def result(item, index, target, outcome, model="hsemotion_enet_b0_8_best_afew", seconds=None):  # noqa: F811
    return PracticeResult(
        id=str(uuid4()), session_id=item.id, step_index=index, target_expression=target, outcome=outcome,
        peak_level=0.9 if outcome == "achieved" else 0.2, relative_to_calibration=True, feedback_visible=True,
        analyzed_frames=10, flagged_frames=0, emotion_model_id=model, emotion_model_version="1",
        started_at=item.started_at, ended_at=item.started_at + timedelta(seconds=10),
        seconds_to_achieve=(seconds or 2.0) if outcome == "achieved" else None)


# --- Protocolo de ejemplo -------------------------------------------------------------------

def test_un_voluntario_en_modo_demo_agrega_el_protocolo_una_sola_vez(env, validation):  # noqa: F811
    status = validation.client.get("/practice-validation/protocol", headers=headers(env, env.user_1)).json()
    assert status == {"available": True, "protocol_id": None}
    created = validation.client.post("/practice-validation/protocol", headers=headers(env, env.user_1))
    assert created.status_code == 201 and created.json()["name"] == VALIDATION_PROTOCOL_NAME
    again = validation.client.post("/practice-validation/protocol", headers=headers(env, env.user_1)).json()
    assert again["protocol_id"] == created.json()["protocol_id"]
    protocol = env.protocols.repository.get(again["protocol_id"])
    assert protocol.for_children is False
    assert [step.target_expression for step in protocol.steps] == list(VALIDATION_TARGETS)
    assert "contempt" not in VALIDATION_TARGETS and len(VALIDATION_TARGETS) == 7
    assert all(step.is_practice and step.stimulus_id is None for step in protocol.steps)
    listed = env.client.get("/protocols", headers=headers(env, env.user_1)).json()
    assert [item["name"] for item in listed] == [VALIDATION_PROTOCOL_NAME]
    # Se aplica desde el Analizador como cualquier protocolo.
    session_id, _ = guided(env, {"id": protocol.id, "for_children": False})
    assert env.sessions.get_session(session_id).protocol_id == protocol.id


@pytest.mark.parametrize("who", ["no_voluntario", "docente_voluntario"])
def test_solo_cuentas_de_voluntario_de_usuario(env, validation, who):  # noqa: F811
    user = env.user_2
    if who == "docente_voluntario":
        volunteer(env, env.docente_a)
        user = env.docente_a
    assert validation.client.get("/practice-validation/protocol", headers=headers(env, user)).json()["available"] is False
    assert validation.client.post("/practice-validation/protocol", headers=headers(env, user)).status_code == 403


@pytest.mark.parametrize("mode", ["development", "production"])
def test_fuera_del_modo_demo_no_se_ofrece_ni_se_aplica(env, validation, mode):  # noqa: F811
    protocol_id = validation.client.post("/practice-validation/protocol",
                                         headers=headers(env, env.user_1)).json()["protocol_id"]
    other = build(env, mode)
    assert other.client.get("/practice-validation/protocol", headers=headers(env, env.user_1)).json()["available"] is False
    assert other.client.post("/practice-validation/protocol", headers=headers(env, env.user_1)).status_code == 403
    accept_commitment(env, env.user_1)
    started = env.client.post("/sessions", headers=headers(env, env.user_1),
                              json={"authorization_confirmed": True, "protocol_id": protocol_id})
    assert started.status_code == 409 and "modo demo" in started.json()["detail"]


def test_el_nombre_esta_reservado(env, validation):  # noqa: F811
    body = {"name": "validación con adultos ", "description": "", "for_children": False,
            "steps": [{"kind": "practice", "target_expression": "happiness", "hold_seconds": 2, "exposure_seconds": 10}]}
    for user in (env.user_1, env.user_2):
        response = env.client.post("/protocols", headers=headers(env, user), json=body)
        assert response.status_code == 422 and "reservado" in response.json()["detail"]
    protocol_id = validation.client.post("/practice-validation/protocol",
                                         headers=headers(env, env.user_1)).json()["protocol_id"]
    renamed = env.client.put(f"/protocols/{protocol_id}", headers=headers(env, env.user_1), json={**body, "name": "Otro"})
    assert renamed.status_code == 422 and "conserva su nombre" in renamed.json()["detail"]
    kept = env.client.put(f"/protocols/{protocol_id}", headers=headers(env, env.user_1),
                          json={**body, "name": VALIDATION_PROTOCOL_NAME})
    assert kept.status_code == 200, kept.text


# --- Exportación agregada --------------------------------------------------------------------

def rows(text):
    return list(csv.reader(io.StringIO(text)))


def test_la_exportacion_es_agregada_y_sin_identificadores(env, validation):  # noqa: F811
    protocol = {"id": validation.client.post("/practice-validation/protocol",
                                             headers=headers(env, env.user_1)).json()["protocol_id"]}
    first = session(env, env.user_1, protocol=protocol)
    second = session(env, env.user_1, day=1, protocol=protocol)
    repository = env.guided.repository
    for item in (result(first, 0, "neutral", "achieved", seconds=1.0), result(first, 1, "happiness", "achieved", seconds=2.0),
                 result(first, 2, "surprise", "timed_out"), result(first, 3, "sadness", "skipped"),
                 result(second, 1, "happiness", "achieved", seconds=4.0), result(second, 2, "surprise", "stopped"),
                 result(second, 0, "neutral", "timed_out", model="ferplus_onnx")):
        repository.save_practice_result(item)
    # Fuera de la validación: otra cuenta (no voluntaria) y otro protocolo del voluntario.
    other = session(env, env.user_2)
    repository.save_practice_result(result(other, 0, "happiness", "achieved"))
    plain = session(env, env.user_1, day=2, protocol=practice_protocol(env, env.user_1, "Otro", "happiness"))
    repository.save_practice_result(result(plain, 0, "happiness", "timed_out"))

    response = validation.client.get("/practice-validation/export.csv", headers=headers(env, env.superadmin))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    table = rows(response.text)
    assert tuple(table[0]) == CSV_HEADER
    assert table[1:] == [
        ["ferplus_onnx", "1", "neutral", "1", "0", ""],
        ["hsemotion_enet_b0_8_best_afew", "1", "neutral", "1", "1", "1.00"],
        ["hsemotion_enet_b0_8_best_afew", "1", "happiness", "2", "2", "3.00"],
        ["hsemotion_enet_b0_8_best_afew", "1", "surprise", "1", "0", ""],
    ]
    for secret in (first.id, second.id, first.code or "S-", "usuario1@example.com", env.user_1.id, protocol["id"]):
        assert secret not in response.text
    assert ("view", "practice_validation", "success") in audit_actions(env)


def test_sin_sesiones_la_exportacion_trae_solo_el_encabezado(env, validation):  # noqa: F811
    response = validation.client.get("/practice-validation/export.csv", headers=headers(env, env.superadmin))
    assert rows(response.text) == [list(CSV_HEADER)]


def test_solo_administracion_exporta(env, validation):  # noqa: F811
    for user in (env.admin, env.docente_a, env.user_1, env.user_2):
        assert validation.client.get("/practice-validation/export.csv", headers=headers(env, user)).status_code == 403
    assert ("view", "practice_validation", "denied") in audit_actions(env)
    assert validation.client.get("/practice-validation/export.csv").status_code == 401


def test_filas_ordenadas_por_modelo_y_expresion():
    item = SimpleNamespace(id="s", started_at=datetime(2026, 10, 30, tzinfo=timezone.utc))
    data = [result(item, 0, "fear", "achieved", seconds=3.0), result(item, 1, "neutral", "achieved", seconds=1.5),
            result(item, 2, "fear", "achieved", seconds=2.0)]
    assert validation_rows(data) == [("hsemotion_enet_b0_8_best_afew", "1", "neutral", 1, 1, "1.50"),
                                     ("hsemotion_enet_b0_8_best_afew", "1", "fear", 2, 2, "2.50")]
