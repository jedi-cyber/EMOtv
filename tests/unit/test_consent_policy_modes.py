from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application.consent_policy_service import ConsentPolicyService, DEMO_POLICY_ID
from emotv.application import AuthenticationService, SessionService
from emotv.config import get_consent_mode
from emotv.domain.consent_policy import ConsentPolicy
from emotv.domain import Role, Student, User
from emotv.infrastructure.persistence.models import Base
from emotv.infrastructure.persistence.postgres_consent_policy_repository import PostgresConsentPolicyRepository
from emotv.infrastructure.persistence import (PostgresUserRepository, PostgresStudentRepository,
                                               PostgresConsentRepository, InMemorySessionRepository)
from emotv.interfaces.web.identity_router import create_identity_router


def repository():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, PostgresConsentPolicyRepository(sessionmaker(engine))


def test_demo_policy_is_seeded_and_replaced_without_erasing_history(tmp_path):
    engine, repo = repository()
    service = ConsentPolicyService(repo, "demo")
    document = tmp_path / "demo.md"
    document.write_text("Texto provisional de demostración", encoding="utf-8")
    service.ensure_demo_policy(document)
    assert service.active().id == DEMO_POLICY_ID
    approved = ConsentPolicy("EMOTV-CONSENT-001:v1.0", "EMOTV-CONSENT-001", "v1.0",
                             "Política institucional", "Texto aprobado de prueba",
                             datetime.now(timezone.utc), approved=True)
    repo.save(approved)
    service.activate(approved.id)
    assert service.active().id == approved.id
    assert repo.get(DEMO_POLICY_ID).is_active is False
    assert len(repo.list_all()) == 2
    engine.dispose()


def test_production_rejects_demo_or_unapproved_policy():
    engine, repo = repository()
    demo = ConsentPolicy(DEMO_POLICY_ID, "EMOTV-CONSENT-DEMO-001", "v0.1", "Demo",
                         "Texto provisional", datetime.now(timezone.utc), is_demo=True)
    repo.save(demo)
    service = ConsentPolicyService(repo, "production")
    with pytest.raises(ValueError):
        service.activate(demo.id)
    repo.activate(demo.id)
    assert service.active() is None
    engine.dispose()


def test_production_environment_cannot_disable_consent():
    assert get_consent_mode({"ENVIRONMENT": "development"}) == "demo"
    assert get_consent_mode({"ENVIRONMENT": "development", "CONSENT_MODE": "development"}) == "development"
    with pytest.raises(ValueError):
        get_consent_mode({"ENVIRONMENT": "production", "CONSENT_MODE": "development"})


def test_student_accepts_new_active_version_and_old_one_becomes_history():
    engine, policies = repository()
    factory = sessionmaker(engine)
    users, students, consents = (PostgresUserRepository(factory),
                                PostgresStudentRepository(factory), PostgresConsentRepository(factory))
    auth = AuthenticationService(users, "consent-flow-test-secret-at-least-32-characters")
    now = datetime.now(timezone.utc)
    admin = users.save(User("admin", "admin@example.org", auth.hash_password("admin-secret-123"), Role.ADMIN, now))
    student = users.save(User("student", "student@example.org", auth.hash_password("student-secret-123"), Role.STUDENT, now))
    students.save(Student("student-profile", student.id, "STU-1"))
    service = ConsentPolicyService(policies, "demo")
    policies.save(ConsentPolicy(DEMO_POLICY_ID, "EMOTV-CONSENT-DEMO-001", "v0.1",
                                "Demo", "Texto de política demo", now, is_demo=True))
    service.activate(DEMO_POLICY_ID)
    app = FastAPI()
    app.include_router(create_identity_router(auth, users, students, consents, service))
    admin_headers = {"Authorization": f"Bearer {auth.create_access_token(admin)}"}
    student_headers = {"Authorization": f"Bearer {auth.create_access_token(student)}"}
    sessions = SessionService(InMemorySessionRepository(), consent_repository=consents,
                              consent_policy_service=service)
    with TestClient(app) as client:
        assert client.get("/consent-policy", headers=student_headers).json()["id"] == DEMO_POLICY_ID
        assert client.post("/students/student-profile/consents", headers=admin_headers,
                           json={"policy_version": DEMO_POLICY_ID}).status_code == 403
        assert client.post("/students/student-profile/consents", headers=student_headers,
                           json={"policy_version": DEMO_POLICY_ID}).status_code == 201
        assert sessions.start_session(student_id="student-profile").student_id == "student-profile"
        created = client.post("/consent-policies", headers=admin_headers, json={
            "code": "EMOTV-CONSENT-001", "version": "v1.0", "title": "Institucional",
            "content": "Texto institucional aprobado de prueba con detalle suficiente",
            "effective_at": now.isoformat(), "approved": True,
        })
        assert created.status_code == 201
        new_id = created.json()["id"]
        assert client.post(f"/consent-policies/{new_id}/activate", headers=admin_headers).status_code == 200
        with pytest.raises(PermissionError):
            sessions.start_session(student_id="student-profile")
        assert client.post("/students/student-profile/consents", headers=student_headers,
                           json={"policy_version": new_id}).status_code == 201
        history = client.get("/students/student-profile/consents", headers=student_headers).json()
        assert len(history) == 2 and sum(item["revoked_at"] is None for item in history) == 1
        assert sessions.start_session(student_id="student-profile").student_id == "student-profile"
    engine.dispose()
