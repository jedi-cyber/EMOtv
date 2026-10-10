"""API y WebSocket con adaptadores SQLAlchemy aislados y procesador determinista."""
from datetime import datetime, timezone
from dataclasses import replace
import time

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
from emotv.config import LiveExpressionSettings
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.expression_router import expression_payload
from tests.integration.test_expressions_api import seeded_items


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


class AdaptiveAnalyzer:
    def analyze(self, frame):
        return "sadness", .9

    def analyze_detailed(self, frame):
        return ("sadness", .9), {"sadness": .9, "neutral": .05, "happiness": .03, "fear": .02}


class FakeClock:
    """Reloj de estabilidad controlado por la prueba (sin esperas reales)."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


CLOCK = FakeClock()
STABLE_FRAMES = 5  # EMOTION_STABILIZER_MIN_SAMPLES por defecto
CATALOG = {item.expression_key: item for item in seeded_items()}


class AdaptiveProcessor(Processor):
    def __init__(self, activity, emotion):
        super().__init__(activity)
        self.emotion = emotion
        self._next_step_index = 0
        self._reported_step_index = 0

    @property
    def current_step(self):
        return self.activity.steps[self._reported_step_index % len(self.activity.steps)]

    def process_frame(self, frame):
        step_count = len(self.activity.steps) * self.activity.repetitions
        self._reported_step_index = self._next_step_index
        completed = self._next_step_index == step_count - 1
        status = EmotionalActivityStatus(
            EmotionalActivityState.COMPLETED if completed else EmotionalActivityState.PERFORMING_EXERCISE,
            "Completada" if completed else "Siguiente postura",
            self.emotion,
            self.activity,
            exercise=ExerciseStatus(
                ExerciseState.COMPLETED if completed else ExerciseState.HOLDING,
                (self._next_step_index + 1) / step_count,
                self._next_step_index + 1,
            ),
            step_index=self._next_step_index,
            step_count=step_count,
            repetition_index=self._next_step_index // len(self.activity.steps),
            repetition_count=self.activity.repetitions,
            steps_completed=self._next_step_index + 1 if completed else self._next_step_index,
            step_elapsed_seconds=0.5,
            step_duration_seconds=self.current_step.duration_seconds,
        )
        self._next_step_index += 1
        return status


@pytest.fixture
def flow(request):
    CLOCK.now = 0.0
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
                                                 reasons=["RAM insuficiente"] if getattr(request, "param", "SUPPORTED") == "BLOCKED" else []),
                                             emotion_analyzer_factory=lambda model_id: AdaptiveAnalyzer(),
                                             adaptive_processor_factory=lambda activity, analyzer, emotion: _adaptive_processor(activity, emotion, processors),
                                             live_settings=LiveExpressionSettings(stable_seconds=1.0, min_confidence=0.5),
                                             live_clock=CLOCK,
                                             expression_info=lambda key: expression_payload(CATALOG.get(key))))
    with TestClient(app) as client:
        yield client, auth, user, other, student, sessions, identity, processors, users
    engine.dispose()


def credentials(auth, user, session_id):
    return dict(type="authenticate", token=auth.create_access_token(user), session_id=session_id, activity_id="arms_up_5s")


def _adaptive_processor(activity, emotion, processors):
    instance = AdaptiveProcessor(activity, emotion)
    processors.append(instance)
    return instance


JPEG = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))[1].tobytes()


def _open_adaptive(client, auth, user, session_id, socket):
    socket.send_json({"type": "authenticate", "token": auth.create_access_token(user),
                      "session_id": session_id, "emotion_model_id": "ferplus_onnx"})
    ready = socket.receive_json()
    assert ready["type"] == "ready" and ready["state"] == "live"


def _live_frames(socket, count=STABLE_FRAMES):
    messages = []
    for _ in range(count):
        socket.send_bytes(JPEG)
        messages.append(socket.receive_json())
    return messages


def _recognize(socket, **extra):
    """Estabiliza, mantiene la expresión 1 s (reloj falso) y la registra."""
    _live_frames(socket)
    CLOCK.now += 1.0
    socket.send_json({"type": "confirm_expression", **extra})
    recognized = socket.receive_json()
    assert recognized["type"] == "recognized"
    recommendation = socket.receive_json()
    assert recommendation["type"] == "recommendation"
    return recognized, recommendation


def _student_session(client, auth, user):
    headers = {"Authorization": f"Bearer {auth.create_access_token(user)}"}
    response = client.post("/sessions", headers=headers, json={})
    assert response.status_code == 201
    return response.json()["id"]


def test_recognize_then_recommend_then_complete_activity(flow):
    client, auth, user, _, student, sessions, _, processors, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        recognized, suggestion = _recognize(socket)
        assert recognized["emotion"] == suggestion["emotion"] == "sadness"
        expression = suggestion["expression"]
        assert expression["expression_key"] == "sadness" and expression["label_es"] == "Tristeza"
        assert {"what_it_is", "why_it_occurs", "facial_cues", "practice_tip", "limitation_note",
                "common_limitation", "review_status"} <= expression.keys()
        assert expression["review_status"] == "draft"
        assert suggestion["activity"]["id"] in {"morning_mobility", "open_and_reach", "arms_up_5s"}
        stored = sessions.get_session(session_id)
        assert stored.state is SessionState.RECOGNIZED and stored.activity_id is None
        socket.send_json({"type": "select_activity", "activity_id": "arms_up_5s"})
        assert socket.receive_json()["type"] == "activity_started"
        assert sessions.get_session(session_id).state is SessionState.IN_PROGRESS
        assert sessions.get_session(session_id).activity_id == "arms_up_5s"
        socket.send_bytes(JPEG)
        completed = socket.receive_json()
        assert completed["type"] == "completed" and completed["exercise_result"] == "completed"
    final = sessions.get_session(session_id)
    assert final.state is SessionState.COMPLETED
    assert final.exercise_result == "completed"
    assert final.initial_emotion == "sadness"
    assert final.recognized_at == stored.recognized_at
    assert processors[-1].closed


def test_live_phase_streams_readings_without_writing_to_database(flow):
    client, auth, user, _, _, sessions, _, processors, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        before = sessions.get_session(session_id)
        writes = []
        original_save = sessions.repository.save
        sessions.repository.save = lambda item: writes.append(item) or original_save(item)
        try:
            messages = _live_frames(socket, STABLE_FRAMES + 2)
        finally:
            sessions.repository.save = original_save
        assert writes == []
        assert sessions.get_session(session_id) == before
    assert all(message["type"] == "live" for message in messages)
    assert messages[0]["emotion"] is None and not messages[0]["can_confirm"]
    last = messages[-1]
    assert last["face_detected"] and last["emotion"] == "sadness"
    assert [item["emotion"] for item in last["top"]] == ["sadness", "neutral", "happiness"]
    assert last["required_stable_seconds"] == 1.0
    assert not last["can_confirm"] and last["blocked_reason"]
    assert not processors


def test_confirmation_requires_stability_and_uses_server_expression(flow):
    client, auth, user, _, _, sessions, _, _, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        _live_frames(socket)
        socket.send_json({"type": "confirm_expression"})
        rejected = socket.receive_json()
        assert rejected["type"] == "confirm_rejected" and "momento" in rejected["message"]
        assert sessions.get_session(session_id).initial_emotion is None
        CLOCK.now += 1.0
        # El cliente intenta imponer otra etiqueta; el servidor la ignora.
        socket.send_json({"type": "confirm_expression", "emotion": "happiness", "emotion_confidence": 1.0})
        recognized = socket.receive_json()
        assert recognized["type"] == "recognized" and recognized["emotion"] == "sadness"
        socket.receive_json()  # recomendación
        stored = sessions.get_session(session_id)
        assert stored.state is SessionState.RECOGNIZED
        assert (stored.initial_emotion, stored.emotion_confidence) == ("sadness", .9)
        assert stored.recognized_at is not None
        socket.send_json({"type": "confirm_expression"})
        assert socket.receive_json()["type"] == "confirm_rejected"  # una sola expresión por sesión


def test_confirmation_without_face_is_rejected(flow):
    client, auth, user, _, _, sessions, _, _, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        socket.send_json({"type": "confirm_expression"})
        rejected = socket.receive_json()
        assert rejected["type"] == "confirm_rejected" and "rostro" in rejected["message"]
    deadline = time.monotonic() + 3  # el cierre ocurre en el hilo del servidor
    while time.monotonic() < deadline and sessions.get_session(session_id).state is SessionState.IN_PROGRESS:
        time.sleep(0.01)
    assert sessions.get_session(session_id).state is SessionState.CANCELLED


def test_confirmation_then_disconnect_keeps_expression(flow):
    client, auth, user, _, _, sessions, _, _, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        _recognize(socket)
    deadline = time.monotonic() + 3  # el cierre ocurre en el hilo del servidor
    while time.monotonic() < deadline and sessions.get_session(session_id).state is SessionState.RECOGNIZED:
        time.sleep(0.01)
    final = sessions.get_session(session_id)
    assert final.state is SessionState.COMPLETED
    assert final.exercise_result == "cancelled"
    assert final.initial_emotion == "sadness" and final.recognized_at is not None


def test_confirmation_then_finish_without_activity(flow):
    client, auth, user, _, _, sessions, _, processors, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        _recognize(socket)
        socket.send_json({"type": "finish_without_activity"})
        finished = socket.receive_json()
        assert finished["type"] == "completed" and finished["exercise_result"] == "skipped"
    final = sessions.get_session(session_id)
    assert final.state is SessionState.COMPLETED
    assert final.exercise_result == "skipped"
    assert final.activity_id is None and final.initial_emotion == "sadness"
    assert not processors


def test_cancel_during_activity_keeps_expression(flow):
    client, auth, user, _, _, sessions, _, _, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        _recognize(socket)
        socket.send_json({"type": "select_activity", "activity_id": "arms_up_5s"})
        assert socket.receive_json()["type"] == "activity_started"
        socket.send_json({"type": "cancel"})
        cancelled = socket.receive_json()
        assert cancelled["type"] == "cancelled" and cancelled["recognition_kept"] is True
    final = sessions.get_session(session_id)
    assert (final.state, final.exercise_result, final.initial_emotion) == (SessionState.COMPLETED, "cancelled", "sadness")


def test_session_without_confirmation_is_still_cancelled(flow):
    client, auth, user, _, _, sessions, _, _, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        _live_frames(socket)
    deadline = time.monotonic() + 3  # el cierre ocurre en el hilo del servidor
    while time.monotonic() < deadline and sessions.get_session(session_id).state is SessionState.IN_PROGRESS:
        time.sleep(0.01)
    final = sessions.get_session(session_id)
    assert final.state is SessionState.CANCELLED
    assert final.initial_emotion is None and final.recognized_at is None


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
        # El finally del servidor corre en otro hilo tras la desconexión.
        deadline = time.monotonic() + 3  # el cierre ocurre en el hilo del servidor
        while time.monotonic() < deadline and (
            sessions.get_session(session.id).state is SessionState.IN_PROGRESS or not processors[-1].closed
        ):
            time.sleep(0.01)
        assert sessions.get_session(session.id).state is SessionState.CANCELLED
        assert processors[-1].closed


def _admin(auth, users):
    return users.save(User("admin-flow", "admin-flow@example.com", auth.hash_password("admin-password-123"),
                           Role.ADMIN, datetime.now(timezone.utc)))


@pytest.mark.parametrize("model_id", ["ferplus_onnx", "hardlyhumans_vit"])
def test_admin_selected_model_reaches_processor(flow, model_id):
    client, auth, _, _, student, sessions, _, processors, users = flow
    admin = _admin(auth, users)
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json({**credentials(auth, admin, session.id), "emotion_model_id": model_id})
        ready = socket.receive_json()
        assert ready["type"] == "ready"
        assert ready["emotion_model_id"] == model_id
    assert processors[-1].model_id == model_id
    deadline = time.monotonic() + 3  # el cierre ocurre en el hilo del servidor
    while time.monotonic() < deadline and (
        not processors[-1].closed
        or sessions.get_session(session.id).state is SessionState.IN_PROGRESS
    ):
        time.sleep(0.01)
    assert processors[-1].closed
    assert sessions.get_session(session.id).state is SessionState.CANCELLED
    assert sessions.get_session(session.id).emotion_model_id == model_id
    assert sessions.get_session(session.id).emotion_model_version == EmotionModelCatalog().get(model_id).version


def test_recommended_sequence_uses_same_session_and_exposes_every_step(flow):
    client, auth, user, _, _, sessions, _, processors, _ = flow
    headers = {"Authorization": f"Bearer {auth.create_access_token(user)}"}
    session_id = client.post("/sessions", headers=headers, json={}).json()["id"]
    jpeg = np.frombuffer(JPEG, dtype=np.uint8)

    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        _, recommendation = _recognize(socket)
        activity = recommendation["activity"]
        assert recommendation["type"] == "recommendation"
        assert len(activity["steps"]) >= 2
        assert sessions.get_session(session_id).activity_id is None

        socket.send_json({"type": "select_activity", "activity_id": activity["id"]})
        started = socket.receive_json()
        assert started["type"] == "activity_started"
        assert started["activity"]["steps"] == activity["steps"]
        assert sessions.get_session(session_id).id == session_id
        assert sessions.get_session(session_id).activity_id == activity["id"]

        received_steps = []
        for expected_index, expected_step in enumerate(activity["steps"]):
            socket.send_bytes(jpeg.tobytes())
            update = socket.receive_json()
            received_steps.append(update["step"])
            assert update["step_index"] == expected_index
            assert update["step_count"] == len(activity["steps"])
            assert update["repetition_index"] == 0 and update["repetition_count"] == 1
            assert update["step_remaining_seconds"] == expected_step["duration_seconds"] - 0.5
            assert update["step"] == expected_step
            assert update["type"] == ("completed" if expected_index == len(activity["steps"]) - 1 else "status")

    assert received_steps == activity["steps"]
    final = sessions.get_session(session_id)
    assert final.state is SessionState.COMPLETED
    assert final.exercise_steps_completed == final.exercise_steps_total == len(activity["steps"])
    assert processors[-1].closed


def test_interrupted_sequence_keeps_the_step_reached(flow):
    client, auth, user, _, _, sessions, _, _, _ = flow
    session_id = _student_session(client, auth, user)
    with client.websocket_connect("/ws/activity") as socket:
        _open_adaptive(client, auth, user, session_id, socket)
        _, recommendation = _recognize(socket)
        activity = recommendation["activity"]
        socket.send_json({"type": "select_activity", "activity_id": activity["id"]})
        assert socket.receive_json()["type"] == "activity_started"
        for _ in range(2):
            socket.send_bytes(JPEG)
            assert socket.receive_json()["type"] == "status"
        assert sessions.get_session(session_id).exercise_steps_completed == 1
    final = sessions.get_session(session_id)
    assert (final.state, final.exercise_result) == (SessionState.COMPLETED, "cancelled")
    assert final.exercise_steps_completed == 1
    assert final.exercise_steps_total == len(activity["steps"]) * activity["repetitions"]
    assert final.exercise_repetitions == activity["repetitions"]


def test_student_cannot_choose_non_default_model(flow):
    client, auth, user, _, student, sessions, _, processors, _ = flow
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json({**credentials(auth, user, session.id), "emotion_model_id": "hardlyhumans_vit"})
        error = socket.receive_json()
        assert error["type"] == "error"
        assert error["code"] == 4403
    assert not processors
    assert sessions.get_session(session.id).emotion_model_id is None


def test_student_without_model_id_uses_ferplus(flow):
    client, auth, user, _, student, sessions, _, processors, _ = flow
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    with client.websocket_connect("/ws/activity") as socket:
        socket.send_json(credentials(auth, user, session.id))
        assert socket.receive_json()["emotion_model_id"] == "ferplus_onnx"
    assert processors[-1].model_id == "ferplus_onnx"


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
    client, auth, user, _, student, sessions, _, processors, users = flow
    assert client.get("/analysis/models").status_code == 401
    student_headers = {"Authorization": f"Bearer {auth.create_access_token(user)}"}
    assert client.get("/analysis/models", headers=student_headers).status_code == 403
    admin_headers = {"Authorization": f"Bearer {auth.create_access_token(_admin(auth, users))}"}
    assert client.get("/analysis/models", headers=admin_headers).json()[0]["state"] == "BLOCKED"
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
