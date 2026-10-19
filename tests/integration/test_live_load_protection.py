"""Protección de carga de la lectura en vivo, con detector y clasificador falsos.

Ninguna prueba usa pesos ni red. El analizador falso puede quedarse "pensando"
hasta que la prueba lo libere, para simular un análisis lento.
"""
import threading
import time

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import ActivityCatalog, AuthenticationService, IdentityRegistrationService, SessionService
from emotv.config import ServerLoadSettings
from emotv.domain import SessionState
from emotv.infrastructure.persistence import (
    Base, PostgresConsentRepository, PostgresSessionRepository, PostgresStudentRepository, PostgresUserRepository,
)
from emotv.interfaces.web.analysis_capacity import AnalysisCapacity, SERVER_BUSY_MESSAGE
from emotv.interfaces.web.analysis_router import IDLE_CLOSE_CODE, IDLE_MESSAGE, create_analysis_router
from emotv.interfaces.web.session_router import create_session_router

JPEG = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))[1].tobytes()


class SlowAnalyzer:
    """Analizador falso: cuenta llamadas y espera una compuerta si está cerrada."""

    def __init__(self):
        self.calls = 0
        self.gate = threading.Event()
        self.gate.set()
        self.started = threading.Event()
        self.threads = []

    def analyze(self, frame):
        return self.analyze_detailed(frame)[0]

    def analyze_detailed(self, frame):
        self.calls += 1
        self.threads.append(threading.current_thread().name)
        self.started.set()
        assert self.gate.wait(10), "la prueba no liberó el análisis"
        return ("neutral", .9), {"neutral": .9, "happiness": .1}


def build(load: ServerLoadSettings):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users, students, consents = PostgresUserRepository(factory), PostgresStudentRepository(factory), PostgresConsentRepository(factory)
    auth = AuthenticationService(users, "load-protection-secret-at-least-32-chars")
    identity = IdentityRegistrationService(users, students, consents, auth)
    accounts = []
    for index in range(3):
        user, student = identity.register_student(f"load{index}@example.com", "load-password-123", f"code-load-{index}")
        identity.grant_consent(student.id, "test-v1")
        accounts.append(user)
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
    analyzers = []

    def analyzer_factory(model_id):
        analyzer = SlowAnalyzer()
        analyzers.append(analyzer)
        return analyzer

    app = FastAPI()
    app.include_router(create_session_router(sessions, auth, users, students, activities=ActivityCatalog()))
    app.include_router(create_analysis_router(
        sessions, ActivityCatalog(), auth, users, students, lambda activity: None,
        emotion_analyzer_factory=analyzer_factory,
        adaptive_processor_factory=lambda activity, analyzer, emotion: None,
        capacity=AnalysisCapacity(load),
    ))

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app, auth, accounts, sessions, analyzers, engine


@pytest.fixture
def server(request):
    load = getattr(request, "param", ServerLoadSettings(max_concurrent_analyses=2, max_active_sessions=3,
                                                        busy_wait_seconds=0.3, idle_timeout_seconds=30))
    app, auth, accounts, sessions, analyzers, engine = build(load)
    with TestClient(app) as client:
        yield client, auth, accounts, sessions, analyzers
    engine.dispose()


def _wait_cancelled(sessions, session_id):
    # El cierre ocurre en el hilo del servidor después de que el cliente sale.
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and sessions.get_session(session_id).state is SessionState.IN_PROGRESS:
        time.sleep(0.02)
    assert sessions.get_session(session_id).state is SessionState.CANCELLED


def _open(client, auth, user, socket):
    token = auth.create_access_token(user)
    session_id = client.post("/sessions", headers={"Authorization": f"Bearer {token}"}, json={}).json()["id"]
    socket.send_json({"type": "authenticate", "token": token, "session_id": session_id})
    return session_id, socket.receive_json()


def test_frames_that_arrive_during_an_analysis_are_dropped(server):
    client, auth, accounts, _, analyzers = server
    with client.websocket_connect("/ws/activity") as socket:
        _, ready = _open(client, auth, accounts[0], socket)
        assert ready["type"] == "ready"
        analyzer = analyzers[-1]
        analyzer.gate.clear()
        for _ in range(4):  # un cuadro en análisis y tres que llegan mientras tanto
            socket.send_bytes(JPEG)
        assert analyzer.started.wait(5)
        time.sleep(0.3)  # el lector recibe y descarta los otros tres
        analyzer.gate.set()
        assert socket.receive_json()["type"] == "live"
        # Si se hubieran encolado cuadros, llegarían más lecturas antes de esta respuesta.
        socket.send_json({"type": "calibrate"})
        assert socket.receive_json()["type"] == "calibration_started"
        assert analyzer.calls == 1
        # Resuelto el cuadro anterior, el siguiente sí se analiza.
        socket.send_bytes(JPEG)
        assert socket.receive_json()["type"] == "live"
        assert analyzer.calls == 2


def test_analysis_runs_in_its_own_pool_and_the_api_keeps_responding(server):
    client, auth, accounts, _, analyzers = server
    with client.websocket_connect("/ws/activity") as socket:
        _open(client, auth, accounts[0], socket)
        analyzer = analyzers[-1]
        analyzer.gate.clear()
        socket.send_bytes(JPEG)
        assert analyzer.started.wait(5)
        answers = []
        caller = threading.Thread(target=lambda: answers.append(client.get("/ping").status_code))
        caller.start()
        caller.join(5)
        assert answers == [200]  # el análisis bloqueado no detiene el bucle de eventos
        analyzer.gate.set()
        assert socket.receive_json()["type"] == "live"
    assert len(analyzer.threads) == 1 and analyzer.threads[0].startswith("emotv-analysis")


@pytest.mark.parametrize("server", [ServerLoadSettings(max_concurrent_analyses=1, max_active_sessions=3,
                                                       busy_wait_seconds=0.3, idle_timeout_seconds=30)],
                         indirect=True)
def test_concurrent_analysis_limit_answers_server_busy(server):
    client, auth, accounts, sessions, analyzers = server
    with client.websocket_connect("/ws/activity") as first, client.websocket_connect("/ws/activity") as second:
        _open(client, auth, accounts[0], first)
        session_id, _ = _open(client, auth, accounts[1], second)
        busy_analyzer = analyzers[0]
        busy_analyzer.gate.clear()
        first.send_bytes(JPEG)
        assert busy_analyzer.started.wait(5)
        second.send_bytes(JPEG)  # el único cupo está ocupado más que la espera permitida
        error = second.receive_json()
        assert error == {"type": "error", "message": SERVER_BUSY_MESSAGE, "code": 1013}
        assert analyzers[1].calls == 0
        busy_analyzer.gate.set()
        assert first.receive_json()["type"] == "live"
    _wait_cancelled(sessions, session_id)


@pytest.mark.parametrize("server", [ServerLoadSettings(max_concurrent_analyses=2, max_active_sessions=1,
                                                       busy_wait_seconds=0.3, idle_timeout_seconds=30)],
                         indirect=True)
def test_active_session_limit_answers_server_busy_and_frees_the_slot(server):
    client, auth, accounts, sessions, analyzers = server
    with client.websocket_connect("/ws/activity") as first:
        _, ready = _open(client, auth, accounts[0], first)
        assert ready["type"] == "ready"
        with client.websocket_connect("/ws/activity") as second:
            session_id, error = _open(client, auth, accounts[1], second)
            assert error == {"type": "error", "message": SERVER_BUSY_MESSAGE, "code": 1013}
        assert len(analyzers) == 1  # sin cupo no se carga el modelo
        _wait_cancelled(sessions, session_id)
    # Al cerrar la primera conexión el cupo queda libre.
    with client.websocket_connect("/ws/activity") as third:
        _, ready = _open(client, auth, accounts[2], third)
        assert ready["type"] == "ready"


@pytest.mark.parametrize("server", [ServerLoadSettings(max_concurrent_analyses=1, max_active_sessions=1,
                                                       busy_wait_seconds=0.3, idle_timeout_seconds=0.4)],
                         indirect=True)
def test_idle_session_is_released(server):
    client, auth, accounts, sessions, _ = server
    with client.websocket_connect("/ws/activity") as socket:
        session_id, ready = _open(client, auth, accounts[0], socket)
        assert ready["type"] == "ready"
        socket.send_bytes(JPEG)
        assert socket.receive_json()["type"] == "live"
        # La pestaña se oculta: no llegan más cuadros.
        error = socket.receive_json()
        assert error == {"type": "error", "message": IDLE_MESSAGE, "code": IDLE_CLOSE_CODE}
    _wait_cancelled(sessions, session_id)
    # Se liberó también el cupo de sesión activa (máximo 1).
    with client.websocket_connect("/ws/activity") as again:
        _, ready = _open(client, auth, accounts[1], again)
        assert ready["type"] == "ready"
