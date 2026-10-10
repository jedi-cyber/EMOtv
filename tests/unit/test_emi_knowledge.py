"""Conocimiento de EMOtv para Emi: contenido, límite de tamaño, caché e invalidación."""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from emotv.application import ActivityCatalog, AuthenticationService
from emotv.application.activity_catalog import DEFAULT_ACTIVITIES
from emotv.application.emi_knowledge import MAX_KNOWLEDGE_CHARS, POSTURES, EmiKnowledge, build_knowledge
from emotv.application.expression_catalog_service import ExpressionCatalogService
from emotv.domain import Activity, PostureId, Role, User
from emotv.domain.activity import ActivityStep
from emotv.domain.expression_info import TEXT_MAX_LENGTH, ReviewStatus
from emotv.infrastructure.persistence import InMemoryExpressionInfoRepository
from emotv.interfaces.web.activity_router import create_activity_router
from emotv.interfaces.web.expression_router import create_expression_router
from tests.integration.test_expressions_api import edit_body, seeded_items
from tests.unit.test_activity_router import FakeUserRepository


def test_knowledge_with_current_content_fits_the_workflow_limit():
    text = build_knowledge(DEFAULT_ACTIVITIES, seeded_items())

    # El workflow EMI corta lo que exceda este límite.
    assert len(text) <= MAX_KNOWLEDGE_CHARS, len(text)
    for name, instruction in POSTURES.values():
        assert name in text and instruction in text
    for activity in DEFAULT_ACTIVITIES:
        assert activity.name in text
    for item in seeded_items():
        assert item.label_es in text
    for heading in ("Qué es:", "Por qué suele presentarse:", "Cómo se reconoce:", "## Flujo de uso",
                    "## Qué se guarda y qué no", "## Roles"):
        assert heading in text
    assert "no es diagnóstico" in text


def test_knowledge_stays_under_limit_with_maximum_admin_content():
    long_text = ("Texto largo de prueba con varias frases. " * 40)[:TEXT_MAX_LENGTH]
    expressions = [replace(item, what_it_is=long_text, why_it_occurs=long_text, facial_cues=long_text)
                   for item in seeded_items()]
    steps = tuple(ActivityStep(posture, long_text[:300], 10) for posture in PostureId)
    activities = [Activity(f"actividad_{index}", f"Actividad {index}", long_text, PostureId.ARMS_UP, 10,
                           repetitions=2, steps=steps) for index in range(40)]

    text = build_knowledge(activities, expressions)

    assert len(text) <= MAX_KNOWLEDGE_CHARS


def test_knowledge_contains_no_user_data():
    reviewed = [replace(item, review_status=ReviewStatus.REVIEWED, reviewed_by_user_id="admin-usuario-123",
                        reviewed_at=datetime.now(timezone.utc)) for item in seeded_items()]
    text = build_knowledge(DEFAULT_ACTIVITIES, reviewed)
    assert "admin-usuario-123" not in text and "@" not in text
    assert "pendiente de revisión" not in text


def test_cache_is_reused_until_invalidated_and_logs_size(caplog):
    calls = []

    def activities():
        calls.append(1)
        return DEFAULT_ACTIVITIES

    knowledge = EmiKnowledge(activities, seeded_items)
    with caplog.at_level(logging.INFO):
        first = knowledge.get()
    assert knowledge.get() == first and len(calls) == 1
    assert f"{len(first)} caracteres" in caplog.text

    knowledge.invalidate()
    knowledge.get()
    assert len(calls) == 2


def test_cache_expires_and_survives_database_errors():
    now = [0.0]
    fail = [False]

    def activities():
        if fail[0]:
            raise RuntimeError("base no disponible")
        return DEFAULT_ACTIVITIES

    knowledge = EmiKnowledge(activities, seeded_items, cache_seconds=60, clock=lambda: now[0])
    first = knowledge.get()
    fail[0] = True
    now[0] = 61
    assert knowledge.get() == first  # sin base, se conserva el último texto
    assert EmiKnowledge(activities, seeded_items).get() == ""


def _admin():
    users = FakeUserRepository()
    auth = AuthenticationService(users, "emi-knowledge-test-secret-at-least-32-chars")
    admin = users.save(User("admin", "admin@example.com", "hash", Role.ADMIN, datetime.now(timezone.utc)))
    return users, auth, {"Authorization": f"Bearer {auth.create_access_token(admin)}"}


def test_editing_activities_or_catalog_invalidates_the_cache():
    users, auth, headers = _admin()
    catalog = ActivityCatalog(())
    repository = InMemoryExpressionInfoRepository(seeded_items())
    knowledge = EmiKnowledge(catalog.list_all, ExpressionCatalogService(repository).list_all)
    app = FastAPI()
    app.include_router(create_activity_router(catalog, auth, users, on_change=knowledge.invalidate))
    app.include_router(create_expression_router(ExpressionCatalogService(repository), auth, users,
                                                on_change=knowledge.invalidate))
    client = TestClient(app)
    assert "Respiración nueva" not in knowledge.get()

    created = client.post("/activities", headers=headers, json={
        "id": "nueva", "name": "Respiración nueva", "description": "Abre los brazos con calma.",
        "required_posture": "arms_open", "duration_seconds": 5, "repetitions": 1})
    assert created.status_code == 201
    assert "Respiración nueva" in knowledge.get()

    body = edit_body(what_it_is="La tristeza es un texto editado por administración para Emi.")
    assert client.put("/expressions/sadness", headers=headers, json=body).status_code == 200
    assert "editado por administración para Emi" in knowledge.get()

    assert client.delete("/activities/nueva", headers=headers).status_code == 204
    assert "Respiración nueva" not in knowledge.get()
