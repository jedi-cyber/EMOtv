"""Política demo vigente: re-aceptación desde una demo anterior, flujo demo y modo development."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import ActivityCatalog, AuthenticationService, IdentityRegistrationService, SessionService
from emotv.application.consent_policy_service import ConsentPolicyService, DEMO_POLICY_ID
from emotv.config import BASE_DIR
from emotv.domain.consent_policy import ConsentPolicy
from emotv.domain.emotional_activity_status import EmotionalActivityState, EmotionalActivityStatus
from emotv.domain.exercise_status import ExerciseState, ExerciseStatus
from emotv.domain.stabilized_emotion import StabilizedEmotion
from emotv.infrastructure.persistence import (Base, PostgresConsentRepository, PostgresSessionRepository,
                                               PostgresStudentRepository, PostgresUserRepository)
from emotv.infrastructure.persistence.postgres_consent_policy_repository import PostgresConsentPolicyRepository
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.identity_router import create_identity_router
from emotv.interfaces.web.session_router import create_session_router

DEMO_DOCUMENT = BASE_DIR / "docs" / "consent-demo.md"
V01_ID = "EMOTV-CONSENT-DEMO-001:v0.1"
V01_TEXT = "Texto original de la política provisional v0.1"
ACTIVITY = "arms_up_5s"


class CompletingProcessor:
    last_pose_result = None

    def __init__(self, activity):
        self.activity = activity

    def process_frame(self, frame):
        return EmotionalActivityStatus(EmotionalActivityState.COMPLETED, "Completada",
                                       StabilizedEmotion("neutral", .9, 1, 1, 1), self.activity,
                                       exercise=ExerciseStatus(ExerciseState.COMPLETED, 1, 5))

    def close(self):
        pass


@contextmanager
def system(mode: str):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users, students, consents = (PostgresUserRepository(factory), PostgresStudentRepository(factory),
                                 PostgresConsentRepository(factory))
    policies = PostgresConsentPolicyRepository(factory)
    policy_service = ConsentPolicyService(policies, mode)
    auth = AuthenticationService(users, "consent-v02-test-secret-at-least-32-chars")
    identity = IdentityRegistrationService(users, students, consents, auth)
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents,
                              consent_policy_service=policy_service)
    catalog = ActivityCatalog()
    app = FastAPI()
    app.include_router(create_identity_router(auth, users, students, consents, policy_service))
    app.include_router(create_session_router(sessions, auth, users, students, activities=catalog))
    app.include_router(create_analysis_router(sessions, catalog, auth, users, students, CompletingProcessor))
    with TestClient(app) as client:
        yield client, auth, identity, policies, policy_service
    engine.dispose()


def new_student(identity, auth, code):
    user, student = identity.register_student(f"{code.lower()}@example.org", "student-secret-123", code)
    return student, {"Authorization": f"Bearer {auth.create_access_token(user)}"}, auth.create_access_token(user)


def accept(client, student, headers, policy_id):
    return client.post(f"/students/{student.id}/consents", headers=headers, json={"policy_version": policy_id})


def start(client, headers):
    return client.post("/sessions", headers=headers, json={"activity_id": ACTIVITY})


def analyze(client, token, session_id):
    """Devuelve el tipo y mensaje del primer resultado tras enviar un frame."""
    _, jpeg = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json({"type": "authenticate", "token": token, "session_id": session_id,
                          "activity_id": ACTIVITY})
        assert socket.receive_json()["type"] == "ready"
        socket.send_bytes(jpeg.tobytes())
        result = socket.receive_json()
    return result["type"], result.get("message", "")


def test_v01_consent_cannot_analyze_until_v02_is_accepted():
    with system("demo") as (client, auth, identity, policies, service):
        policies.save(ConsentPolicy(V01_ID, "EMOTV-CONSENT-DEMO-001", "v0.1", "Demo v0.1", V01_TEXT,
                                    datetime.now(timezone.utc), is_demo=True))
        policies.activate(V01_ID)
        student, headers, token = new_student(identity, auth, "PRUEBA-01")
        assert accept(client, student, headers, V01_ID).status_code == 201
        before_upgrade = start(client, headers)
        assert before_upgrade.status_code == 201

        service.ensure_demo_policy(DEMO_DOCUMENT)

        assert service.active().id == DEMO_POLICY_ID
        legacy = policies.get(V01_ID)
        assert legacy.content == V01_TEXT and legacy.version == "v0.1" and not legacy.is_active
        assert start(client, headers).status_code == 403
        assert analyze(client, token, before_upgrade.json()["id"]) == ("error", "Consentimiento revocado")

        assert accept(client, student, headers, DEMO_POLICY_ID).status_code == 201
        session = start(client, headers)
        assert session.status_code == 201
        assert analyze(client, token, session.json()["id"])[0] == "completed"

        service.ensure_demo_policy(DEMO_DOCUMENT)
        assert service.active().id == DEMO_POLICY_ID and len(policies.list_all()) == 2


def test_demo_new_account_accepts_v02_and_analyzes():
    with system("demo") as (client, auth, identity, policies, service):
        service.ensure_demo_policy(DEMO_DOCUMENT)
        student, headers, token = new_student(identity, auth, "PRUEBA-02")
        policy = client.get("/consent-policy", headers=headers).json()
        assert policy["id"] == DEMO_POLICY_ID and policy["version"] == "v0.3" and policy["is_demo"]
        assert policy["effective_at"] and "EMOTV-CONSENT-DEMO-003" in policy["content"]
        assert start(client, headers).status_code == 403

        assert accept(client, student, headers, policy["id"]).status_code == 201
        session = start(client, headers)
        assert session.status_code == 201
        assert analyze(client, token, session.json()["id"])[0] == "completed"


def test_development_mode_does_not_require_consent():
    with system("development") as (client, auth, identity, policies, service):
        service.ensure_demo_policy(DEMO_DOCUMENT)
        assert policies.list_all() == ()
        student, headers, token = new_student(identity, auth, "PRUEBA-03")
        session = start(client, headers)
        assert session.status_code == 201
        assert analyze(client, token, session.json()["id"])[0] == "completed"


def test_demo_upgrade_never_replaces_institutional_policy():
    with system("demo") as (_, _, _, policies, service):
        institutional = ConsentPolicy("EMOTV-CONSENT-001:v1.0", "EMOTV-CONSENT-001", "v1.0", "Institucional",
                                      "Texto institucional aprobado de prueba", datetime.now(timezone.utc),
                                      approved=True)
        policies.save(institutional)
        policies.activate(institutional.id)
        service.ensure_demo_policy(DEMO_DOCUMENT)
        assert service.active().id == institutional.id
        assert policies.get(DEMO_POLICY_ID) is None
