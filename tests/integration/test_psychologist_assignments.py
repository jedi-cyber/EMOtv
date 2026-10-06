"""Psicología solo accede a los estudiantes que administración le asignó."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import (ActivityCatalog, AuthenticationService, AuthorizationService,
                               IdentityRegistrationService, SessionService)
from emotv.domain import Role
from emotv.domain.psychologist_assignment import PsychologistAssignment
from emotv.infrastructure.persistence import (Base, InMemoryAssignmentRepository, PostgresAssignmentRepository,
                                               PostgresConsentRepository, PostgresSessionRepository,
                                               PostgresStudentRepository, PostgresUserRepository)
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.identity_router import create_identity_router
from emotv.interfaces.web.session_router import create_session_router

JWT_TEST_VALUE = "assignment-tests-jwt-value-at-least-32-chars"
LOCAL_VALUE = "local-test-value-123"


class World:
    def __init__(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        factory = sessionmaker(self.engine, expire_on_commit=False)
        users, students, consents = (PostgresUserRepository(factory), PostgresStudentRepository(factory),
                                     PostgresConsentRepository(factory))
        self.auth = AuthenticationService(users, JWT_TEST_VALUE)
        identity = IdentityRegistrationService(users, students, consents, self.auth)
        self.assignments = PostgresAssignmentRepository(factory)
        policy = AuthorizationService(self.assignments.is_assigned)
        self.sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
        catalog = ActivityCatalog()

        self.admin = identity.register_user("admin@ejemplo.local", LOCAL_VALUE, Role.ADMIN)
        self.psy_a = identity.register_user("psicologia-a@ejemplo.local", LOCAL_VALUE, Role.PSYCHOLOGIST)
        self.psy_b = identity.register_user("psicologia-b@ejemplo.local", LOCAL_VALUE, Role.PSYCHOLOGIST)
        self.user_1, self.student_1 = identity.register_student("prueba-01@ejemplo.local", LOCAL_VALUE, "PRUEBA-01")
        self.user_2, self.student_2 = identity.register_student("prueba-02@ejemplo.local", LOCAL_VALUE, "PRUEBA-02")
        self.user_3, self.student_3 = identity.register_student("prueba-03@ejemplo.local", LOCAL_VALUE, "PRUEBA-03")
        for student in (self.student_1, self.student_2, self.student_3):
            identity.grant_consent(student.id, "test-v1")
        now = datetime.now(timezone.utc)
        self.assignments.assign(PsychologistAssignment(self.psy_a.id, self.student_1.id, now, self.admin.id))
        self.assignments.assign(PsychologistAssignment(self.psy_b.id, self.student_2.id, now, self.admin.id))
        self.session_1 = self.sessions.start_session(student_id=self.student_1.id, activity_id="arms_up_5s")
        self.session_2 = self.sessions.start_session(student_id=self.student_2.id, activity_id="arms_up_5s")
        self.session_3 = self.sessions.start_session(student_id=self.student_3.id, activity_id="arms_up_5s")

        app = FastAPI()
        app.include_router(create_identity_router(self.auth, users, students, consents,
                                                  assignments=self.assignments))
        app.include_router(create_session_router(self.sessions, self.auth, users, students, authorization=policy,
                                                 activities=catalog, assignments=self.assignments))
        app.include_router(create_analysis_router(self.sessions, catalog, self.auth, users, students,
                                                  lambda activity: None, authorization=policy))
        self.client = TestClient(app)

    def headers(self, user) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.auth.create_access_token(user)}"}


@pytest.fixture
def world():
    instance = World()
    yield instance
    instance.engine.dispose()


def ids(response) -> set[str]:
    return {item["id"] for item in response.json()}


def test_psychologist_cannot_see_student_assigned_to_another(world):
    a = world.headers(world.psy_a)
    student_2 = world.student_2.id

    assert world.client.get(f"/sessions?student_id={student_2}", headers=a).status_code == 403
    assert world.client.get(f"/sessions/{world.session_2.id}", headers=a).status_code == 403
    assert world.client.get(f"/students/{student_2}", headers=a).status_code == 403
    assert world.client.get(f"/students/{student_2}/consents", headers=a).status_code == 403
    assert world.client.get(f"/students/{student_2}/consents/active", headers=a).status_code == 403


def test_psychologist_sees_only_assigned_students_and_sessions(world):
    a = world.headers(world.psy_a)

    assert world.client.get(f"/sessions/{world.session_1.id}", headers=a).status_code == 200
    by_student = world.client.get(f"/sessions?student_id={world.student_1.id}", headers=a)
    assert by_student.status_code == 200 and ids(by_student) == {world.session_1.id}
    assert ids(world.client.get("/sessions", headers=a)) == {world.session_1.id}
    assert ids(world.client.get("/students", headers=a)) == {world.student_1.id}
    assert world.client.get(f"/students/{world.student_1.id}/consents", headers=a).status_code == 200


def test_psychologist_without_assignments_gets_empty_lists(world):
    world.assignments.unassign(world.psy_a.id, world.student_1.id)
    a = world.headers(world.psy_a)

    assert world.client.get("/students", headers=a).json() == []
    assert world.client.get("/sessions", headers=a).json() == []


def test_psychologist_cannot_start_cancel_complete_or_analyze(world):
    a = world.headers(world.psy_a)
    result = dict(initial_emotion="neutral", emotion_confidence=.9, activity_id="arms_up_5s",
                  exercise_result="completed", exercise_duration_seconds=5)

    assert world.client.post("/sessions", headers=a, json={"student_id": world.student_1.id}).status_code == 403
    assert world.client.post(f"/sessions/{world.session_1.id}/cancel", headers=a).status_code == 403
    assert world.client.post(f"/sessions/{world.session_1.id}/complete", headers=a, json=result).status_code == 403
    with world.client.websocket_connect("/ws/activity") as socket:
        socket.send_json({"type": "authenticate", "token": world.auth.create_access_token(world.psy_a),
                          "session_id": world.session_1.id, "activity_id": "arms_up_5s"})
        assert socket.receive_json()["code"] == 4403


def test_admin_sees_everything(world):
    admin = world.headers(world.admin)
    every_session = {world.session_1.id, world.session_2.id, world.session_3.id}

    assert ids(world.client.get("/sessions", headers=admin)) == every_session
    assert ids(world.client.get("/students", headers=admin)) == {
        world.student_1.id, world.student_2.id, world.student_3.id}
    assert world.client.get(f"/sessions/{world.session_2.id}", headers=admin).status_code == 200


def test_student_sees_only_own_sessions(world):
    own = world.headers(world.user_1)

    assert ids(world.client.get("/sessions", headers=own)) == {world.session_1.id}
    assert world.client.get(f"/sessions/{world.session_2.id}", headers=own).status_code == 403
    assert world.client.get(f"/sessions?student_id={world.student_2.id}", headers=own).status_code == 403
    assert ids(world.client.get("/students", headers=own)) == {world.student_1.id}


def test_admin_assigns_lists_and_removes_students(world):
    admin, a = world.headers(world.admin), world.headers(world.psy_a)
    base = f"/users/{world.psy_a.id}/assigned-students"
    student_3 = world.student_3.id

    assert world.client.get(f"/sessions/{world.session_3.id}", headers=a).status_code == 403
    assigned = world.client.put(f"{base}/{student_3}", headers=admin)
    assert assigned.status_code == 200 and assigned.json()["student_code"] == "PRUEBA-03"
    assert world.client.put(f"{base}/{student_3}", headers=admin).status_code == 200  # idempotente
    assert {item["student_code"] for item in world.client.get(base, headers=admin).json()} == {"PRUEBA-01", "PRUEBA-03"}
    assert world.client.get(f"/sessions/{world.session_3.id}", headers=a).status_code == 200

    assert world.client.delete(f"{base}/{student_3}", headers=admin).status_code == 204
    assert world.client.get(f"/sessions/{world.session_3.id}", headers=a).status_code == 403
    assert world.client.delete(f"{base}/{student_3}", headers=admin).status_code == 404


def test_assignment_endpoints_are_admin_only_and_validated(world):
    admin = world.headers(world.admin)
    base = f"/users/{world.psy_a.id}/assigned-students"

    for user in (world.psy_a, world.user_1):
        headers = world.headers(user)
        assert world.client.get(base, headers=headers).status_code == 403
        assert world.client.put(f"{base}/{world.student_2.id}", headers=headers).status_code == 403
        assert world.client.delete(f"{base}/{world.student_1.id}", headers=headers).status_code == 403
    assert world.client.put(f"{base}/no-existe", headers=admin).status_code == 404
    assert world.client.put(f"/users/{world.user_1.id}/assigned-students/{world.student_2.id}",
                            headers=admin).status_code == 422
    assert world.client.get("/users/no-existe/assigned-students", headers=admin).status_code == 404


@pytest.mark.parametrize("repository_kind", ["postgres", "memory"])
def test_assignment_repositories_behave_the_same(world, repository_kind):
    repository = (world.assignments if repository_kind == "postgres" else InMemoryAssignmentRepository())
    psychologist, student = world.psy_b.id, world.student_3.id
    first = PsychologistAssignment(psychologist, student, datetime.now(timezone.utc), world.admin.id)

    repository.assign(first)
    again = repository.assign(PsychologistAssignment(psychologist, student,
                                                     first.assigned_at + timedelta(days=1), None))

    assert again.assigned_by_user_id == world.admin.id
    assert repository.is_assigned(psychologist, student)
    assert student in {item.student_id for item in repository.list_by_psychologist(psychologist)}
    assert repository.unassign(psychologist, student) is True
    assert repository.unassign(psychologist, student) is False
    assert not repository.is_assigned(psychologist, student)
