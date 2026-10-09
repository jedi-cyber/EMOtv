"""Catálogo informativo de expresiones: API, permisos, revisión y textos semilla."""
from __future__ import annotations

import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import AuthenticationService
from emotv.application.expression_catalog_service import ExpressionCatalogService
from emotv.domain import Role, User
from emotv.domain.expression_info import COMMON_LIMITATION, EXPRESSION_KEYS, TEXT_FIELDS, ExpressionInfo
from emotv.infrastructure.persistence import Base, PostgresExpressionInfoRepository, PostgresUserRepository
from emotv.interfaces.web.expression_router import create_expression_router

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "20261008_12_expression_info.py"


def load_seed() -> tuple[dict, ...]:
    spec = importlib.util.spec_from_file_location("expression_info_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SEED


def seeded_items() -> tuple[ExpressionInfo, ...]:
    now = datetime.now(timezone.utc)
    return tuple(ExpressionInfo(**row, updated_at=now) for row in load_seed())


@pytest.fixture
def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    repository = PostgresExpressionInfoRepository(factory)
    for item in seeded_items():
        repository.save(item)
    users = PostgresUserRepository(factory)
    auth = AuthenticationService(users, "expression-catalog-secret-at-least-32-chars")
    accounts = {}
    for role in Role:
        accounts[role] = users.save(User(f"{role.value}-1", f"{role.value}@example.com",
                                         auth.hash_password("password-12345"), role, datetime.now(timezone.utc)))
    app = FastAPI()
    app.include_router(create_expression_router(ExpressionCatalogService(repository), auth, users))
    headers = {role: {"Authorization": f"Bearer {auth.create_access_token(user)}"} for role, user in accounts.items()}
    with TestClient(app) as client:
        yield client, headers, accounts, repository
    engine.dispose()


def edit_body(**overrides):
    body = {
        "label_es": "Tristeza",
        "what_it_is": "La tristeza es una emoción relacionada con la pérdida. Texto revisado por Psicología.",
        "why_it_occurs": "En general aparece ante pérdidas o despedidas. Favorece la reflexión.",
        "facial_cues": "Las cejas internas se elevan. Las comisuras descienden.",
        "practice_tip": "Eleva la parte interna de las cejas. Observa la lectura en vivo.",
        "limitation_note": "La cultura, el contexto, la iluminación y el ángulo influyen. Es una estimación.",
        "review_status": "reviewed",
    }
    return {**body, **overrides}


def test_requires_authentication(api):
    client, *_ = api
    assert client.get("/expressions").status_code == 401
    assert client.get("/expressions/sadness").status_code == 401


@pytest.mark.parametrize("role", list(Role))
def test_any_authenticated_role_reads_catalog_in_model_order(api, role):
    client, headers, _, _ = api
    items = client.get("/expressions", headers=headers[role]).json()
    assert [item["expression_key"] for item in items] == list(EXPRESSION_KEYS)
    assert all(item["review_status"] == "draft" and item["reviewed_at"] is None for item in items)
    assert all(item["common_limitation"] == COMMON_LIMITATION for item in items)
    sadness = client.get("/expressions/sadness", headers=headers[role]).json()
    assert sadness["label_es"] == "Tristeza" and sadness["why_it_occurs"]
    assert client.get("/expressions/joy", headers=headers[role]).status_code == 404


@pytest.mark.parametrize("role", [Role.STUDENT, Role.PSYCHOLOGIST])
def test_only_admin_edits(api, role):
    client, headers, _, repository = api
    before = repository.get("sadness")
    assert client.put("/expressions/sadness", headers=headers[role], json=edit_body()).status_code == 403
    assert repository.get("sadness") == before


def test_admin_marks_reviewed_recording_who_and_when_then_back_to_draft(api):
    client, headers, accounts, repository = api
    response = client.put("/expressions/sadness", headers=headers[Role.ADMIN], json=edit_body())
    assert response.status_code == 200
    reviewed = response.json()
    assert reviewed["review_status"] == "reviewed"
    assert reviewed["reviewed_by_user_id"] == accounts[Role.ADMIN].id
    assert reviewed["reviewed_at"] is not None
    assert repository.get("sadness").what_it_is.endswith("Texto revisado por Psicología.")
    draft = client.put("/expressions/sadness", headers=headers[Role.ADMIN],
                       json=edit_body(review_status="draft")).json()
    assert (draft["review_status"], draft["reviewed_by_user_id"], draft["reviewed_at"]) == ("draft", None, None)
    assert client.put("/expressions/joy", headers=headers[Role.ADMIN], json=edit_body()).status_code == 404


@pytest.mark.parametrize("overrides", [
    {"label_es": ""}, {"label_es": "x" * 61}, {"what_it_is": "Muy corto."},
    {"facial_cues": "x" * 1201}, {"review_status": "approved"},
])
def test_admin_edit_is_validated(api, overrides):
    client, headers, _, repository = api
    before = repository.get("sadness")
    assert client.put("/expressions/sadness", headers=headers[Role.ADMIN], json=edit_body(**overrides)).status_code == 422
    assert repository.get("sadness") == before


def _sentences(text: str) -> int:
    return len([part for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part])


def test_seed_covers_every_ferplus_class_in_draft_with_two_to_four_sentences():
    seed = load_seed()
    assert [row["expression_key"] for row in seed] == list(EXPRESSION_KEYS)
    for row in seed:
        assert "review_status" not in row  # la migración fuerza "draft"
        for field in TEXT_FIELDS:
            assert 2 <= _sentences(row[field]) <= 4, (row["expression_key"], field)


def test_seed_wording_rules():
    forbidden = re.compile(r"diagn|trastorn|terap|tratamiento|patolog|sientes|te pasa|estás", re.IGNORECASE)
    for row in load_seed():
        text = " ".join(row[field] for field in ("label_es", *TEXT_FIELDS))
        assert not forbidden.search(text), row["expression_key"]
        note = row["limitation_note"].lower()
        for factor in ("cultura", "contexto", "iluminación", "ángulo"):
            assert factor in note, (row["expression_key"], factor)
        assert "compatible con" in note
