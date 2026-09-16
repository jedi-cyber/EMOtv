"""API y WebSocket con adaptadores SQLAlchemy aislados y procesador determinista."""
from datetime import datetime, timezone
from dataclasses import replace

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import ActivityCatalog, AuthenticationService, SessionService, IdentityRegistrationService
from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.domain import User, Role, SessionState
from emotv.domain.exercise_status import ExerciseStatus, ExerciseState
from emotv.domain.emotional_activity_status import EmotionalActivityStatus, EmotionalActivityState
from emotv.domain.stabilized_emotion import StabilizedEmotion
from emotv.infrastructure.persistence import Base, PostgresUserRepository, PostgresStudentRepository, PostgresConsentRepository, PostgresSessionRepository
from emotv.interfaces.web.session_router import create_session_router
from emotv.interfaces.web.analysis_router import create_analysis_router


class Processor:
    last_pose_result = None

    def __init__(self, activity):
        self.activity, self.closed = activity, False

    def process_frame(self, frame):
        return EmotionalActivityStatus(EmotionalActivityState.COMPLETED, "Completada",
            StabilizedEmotion("neutral", .9, 1, 1, 1), self.activity,
            exercise=ExerciseStatus(ExerciseState.COMPLETED, 1, 5))

    def close(self):
        self.closed = True


@pytest.fixture
def flow(request):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users, students, consents = PostgresUserRepository(factory), PostgresStudentRepository(factory), PostgresConsentRepository(factory)
    auth = AuthenticationService(users, "browser-flow-secret-at-least-32-characters")
    identity = IdentityRegistrationService(users, students, consents, auth)
    user, student = identity.register_student("flow@example.com", "flow-password-123", "code-flow")
    other, _ = identity.register_student("other@example.com", "other-password-123", "code-other")
    identity.grant_consent(student.id, "test-v1")
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
    catalog = ActivityCatalog()
    processors = []
    def processor(activity):
        instance = Processor(activity)
        processors.append(instance)
        return instance
    app = FastAPI()
    app.include_router(create_session_router(sessions, auth, users, students, activities=catalog))
    def model_processor(activity, model_id):
        instance = processor(activity)
        instance.model_id = model_id
        return instance
    app.include_router(create_analysis_router(sessions, catalog, auth, users, students, processor,
                                             model_processor_factory=model_processor,
                                             model_admission=lambda model_id: dict(model_id=model_id,
                                                 state=getattr(request, "param", "SUPPORTED"),
                                                 reasons=["RAM insuficiente"] if getattr(request, "param", "SUPPORTED") == "BLOCKED" else [])))
    with TestClient(app) as client:
        yield client, auth, user, other, student, sessions, identity, processors, users
    engine.dispose()


def credentials(auth, user, session_id):
    return dict(type="authenticate", token=auth.create_access_token(user), session_id=session_id, activity_id="arms_up_5s")


def test_start_complete_and_reject_cancel_of_completed_session(flow):
    client, auth, user, _, student, sessions, _, processors, _ = flow
    headers = {"Authorization": f"Bearer {auth.create_access_token(user)}"}
    response = client.post("/sessions", headers=headers, json={"activity_id": "arms_up_5s"})
    assert response.status_code == 201
    session_id = response.json()["id"]
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json(credentials(auth, user, session_id))
        assert socket.receive_json()["type"] == "ready"
        _, jpeg = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
        socket.send_bytes(jpeg.tobytes())
        assert socket.receive_json()["type"] == "completed"
    assert sessions.get_session(session_id).state is SessionState.COMPLETED
    assert sessions.get_session(session_id).emotion_model_id == "ferplus_onnx"
    assert client.get(f"/sessions/{session_id}", headers=headers).json()["emotion_model_version"] == "1.0"
    assert processors[0].closed
    assert client.post(f"/sessions/{session_id}/cancel", headers=headers).status_code == 409


def test_socket_cancel_and_disconnect_release_resources(flow):
    client, auth, user, _, student, sessions, _, processors, _ = flow
    for command in ("cancel", "disconnect"):
        session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
        with client.websocket_connect("/ws/activity") as socket:
            socket.send_json(credentials(auth, user, session.id))
            assert socket.receive_json()["type"] == "ready"
            if command == "cancel":
                socket.send_json({"type": "cancel"})
                assert socket.receive_json()["type"] == "cancelled"
        assert sessions.get_session(session.id).state is SessionState.CANCELLED
        assert processors[-1].closed


@pytest.mark.parametrize("model_id", ["ferplus_onnx", "hardlyhumans_vit"])
def test_selected_model_reaches_processor(flow, model_id):
    client, auth, user, _, student, sessions, _, processors, _ = flow
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json({**credentials(auth, user, session.id), "emotion_model_id": model_id})
        ready = socket.receive_json()
        assert ready["type"] == "ready"
        assert ready["emotion_model_id"] == model_id
    assert processors[-1].model_id == model_id
    assert processors[-1].closed
    assert sessions.get_session(session.id).state is SessionState.CANCELLED
    assert sessions.get_session(session.id).emotion_model_id == model_id
    assert sessions.get_session(session.id).emotion_model_version == EmotionModelCatalog().get(model_id).version


def test_invalid_model_is_rejected_without_loading(flow):
    client, auth, user, _, student, sessions, _, processors, _ = flow
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json({**credentials(auth, user, session.id), "emotion_model_id": "untrusted/model"})
        assert socket.receive_json()["type"] == "error"
    assert not processors
    assert sessions.get_session(session.id).state is SessionState.CANCELLED
    assert sessions.get_session(session.id).emotion_model_id is None


@pytest.mark.parametrize("flow", ["BLOCKED"], indirect=True)
def test_admission_blocks_socket_and_exposes_authenticated_status(flow):
    client, auth, user, _, student, sessions, _, processors, _ = flow
    assert client.get("/analysis/models").status_code == 401
    headers = {"Authorization": f"Bearer {auth.create_access_token(user)}"}
    assert client.get("/analysis/models", headers=headers).json()[0]["state"] == "BLOCKED"
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json(credentials(auth, user, session.id))
        error = socket.receive_json()
        assert error["type"] == "error"
        assert error["admission"]["state"] == "BLOCKED"
    assert not processors
    assert sessions.get_session(session.id).state is SessionState.CANCELLED


def test_foreign_student_cannot_view_cancel_or_process_session(flow):
    client, auth, user, other, student, sessions, _, processors, _ = flow
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    headers = {"Authorization": f"Bearer {auth.create_access_token(other)}"}
    assert client.get(f"/sessions/{session.id}", headers=headers).status_code == 403
    assert client.post(f"/sessions/{session.id}/cancel", headers=headers).status_code == 403
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json(credentials(auth, other, session.id))
        assert socket.receive_json()["type"] == "error"
    assert not processors
    assert sessions.get_session(session.id).state is SessionState.IN_PROGRESS


@pytest.mark.parametrize("reason", ["consent", "account"])
def test_revocation_during_analysis_prevents_completion(flow, reason):
    client, auth, user, _, student, sessions, identity, processors, users = flow
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json(credentials(auth, user, session.id))
        assert socket.receive_json()["type"] == "ready"
        if reason == "consent":
            identity.revoke_consent(student.id)
        else:
            users.save(replace(user, is_active=False))
        _, jpeg = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
        socket.send_bytes(jpeg.tobytes())
        assert socket.receive_json()["type"] == "error"
    assert sessions.get_session(session.id).state is SessionState.CANCELLED
    assert processors[0].closed
