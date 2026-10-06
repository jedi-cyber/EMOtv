"""Límite de intentos, respuesta uniforme, política de contraseñas y token en el WebSocket."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import ActivityCatalog, AuthenticationService, IdentityRegistrationService, SessionService
from emotv.application.login_throttle import LoginThrottle, hash_email
from emotv.config import LoginLimits, get_login_limits
from emotv.domain import Role, SessionState, User
from emotv.infrastructure.persistence import (Base, PostgresConsentRepository, PostgresLoginAttemptRepository,
                                               PostgresSessionRepository, PostgresStudentRepository,
                                               PostgresUserRepository)
from emotv.infrastructure.persistence.models import LoginAttemptRecord
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.auth_router import LOGIN_FAILED_DETAIL, LOGIN_THROTTLED_DETAIL, create_auth_router
from emotv.interfaces.web.security import configure_web_security, load_web_settings

JWT_TEST_VALUE = "login-hardening-test-jwt-value-32-characters"
GOOD = "valid-local-value-123"
BAD = "wrong-local-value-123"
NEW_VALUE = "otra-clave-larga-456"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


class System:
    def __init__(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.users = PostgresUserRepository(self.factory)
        self.auth = AuthenticationService(self.users, JWT_TEST_VALUE)
        self.clock = Clock()
        self.throttle = LoginThrottle(PostgresLoginAttemptRepository(self.factory),
                                      LoginLimits(max_failures_per_account=5, max_failures_per_ip=20,
                                                  window_minutes=15), clock=self.clock)
        self.app = FastAPI()
        self.app.include_router(create_auth_router(self.auth, self.users, login_throttle=self.throttle))
        now = datetime.now(timezone.utc)
        self.users.save(User("u1", "ana@ejemplo.local", self.auth.hash_password(GOOD), Role.ADMIN, now))
        self.users.save(User("u2", "inactiva@ejemplo.local", self.auth.hash_password(GOOD), Role.ADMIN, now,
                             is_active=False))

    def client(self, ip: str = "10.0.0.1") -> TestClient:
        return TestClient(self.app, client=(ip, 50000))

    def rows(self) -> list[LoginAttemptRecord]:
        with self.factory() as db:
            return list(db.scalars(select(LoginAttemptRecord)))


@pytest.fixture
def system():
    instance = System()
    yield instance
    instance.engine.dispose()


def login(client: TestClient, email: str, password: str):
    return client.post("/auth/token", data={"username": email, "password": password})


def test_account_limit_returns_429_even_with_correct_password(system):
    client = system.client()
    for _ in range(5):
        assert login(client, "ana@ejemplo.local", BAD).status_code == 401

    blocked = login(client, "ana@ejemplo.local", GOOD)

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == LOGIN_THROTTLED_DETAIL
    assert blocked.headers["retry-after"] == "900"
    assert login(system.client("10.0.0.2"), "ana@ejemplo.local", GOOD).status_code == 200


def test_ip_limit_returns_the_same_generic_429(system):
    client = system.client()
    for index in range(20):
        assert login(client, f"nadie{index}@ejemplo.local", BAD).status_code == 401

    blocked = login(client, "ana@ejemplo.local", GOOD)

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == LOGIN_THROTTLED_DETAIL


def test_successful_login_resets_account_counter_but_not_ip_counter(system):
    client = system.client()
    for _ in range(4):
        login(client, "ana@ejemplo.local", BAD)
    assert login(client, "ana@ejemplo.local", GOOD).status_code == 200

    for _ in range(4):
        assert login(client, "ana@ejemplo.local", BAD).status_code == 401
    assert login(client, "ana@ejemplo.local", GOOD).status_code == 200
    assert system.throttle.repository.count_ip_failures("10.0.0.1", system.clock() - timedelta(minutes=15)) == 8


def test_counter_expires_after_the_window(system):
    client = system.client()
    for _ in range(5):
        login(client, "ana@ejemplo.local", BAD)
    assert login(client, "ana@ejemplo.local", GOOD).status_code == 429

    system.clock.advance(minutes=16)

    assert login(client, "ana@ejemplo.local", GOOD).status_code == 200


def test_blocked_attempts_are_not_recorded_and_email_is_hashed(system):
    client = system.client()
    for _ in range(7):
        login(client, "Ana@Ejemplo.local ", BAD)

    rows = system.rows()
    assert len(rows) == 5
    assert {row.email_hash for row in rows} == {hashlib.sha256(b"ana@ejemplo.local").hexdigest()}
    assert all("ana" not in row.email_hash for row in rows)


def test_records_older_than_24_hours_are_purged_on_insert(system):
    client = system.client()
    login(client, "ana@ejemplo.local", BAD)
    system.clock.advance(hours=25)

    login(client, "ana@ejemplo.local", BAD)

    assert len(system.rows()) == 1


def test_unknown_user_wrong_password_and_inactive_get_identical_401(system, monkeypatch):
    calls = []
    original = system.auth.passwords.verify
    monkeypatch.setattr(system.auth.passwords, "verify",
                        lambda password, hashed: calls.append(hashed) or original(password, hashed))
    client = system.client()

    responses = [login(client, "nadie@ejemplo.local", GOOD),
                 login(client, "ana@ejemplo.local", BAD),
                 login(client, "inactiva@ejemplo.local", GOOD)]

    assert {response.status_code for response in responses} == {401}
    assert {response.text for response in responses} == {f'{{"detail":"{LOGIN_FAILED_DETAIL}"}}'}
    assert {response.headers.get("www-authenticate") for response in responses} == {"Bearer"}
    # Los tres casos verifican un hash argon2 (uno ficticio si el usuario no existe).
    assert len(calls) == 3 and all(hashed.startswith("$argon2") for hashed in calls)


@pytest.mark.parametrize(("new_password", "message"), [
    ("corta-123", "La contraseña debe tener al menos 12 caracteres."),
    ("ANA@ejemplo.local", "La contraseña no puede ser igual a tu correo."),
    (GOOD, "La nueva contraseña debe ser diferente de la anterior."),
])
def test_password_policy_on_change_and_first_access(system, new_password, message):
    for must_change in (False, True):
        user = system.users.get_by_email("ana@ejemplo.local")
        system.users.save(User(user.id, user.email, user.password_hash, user.role, user.created_at,
                               must_change_password=must_change, token_version=user.token_version))
        headers = {"Authorization": f"Bearer {system.auth.create_access_token(system.users.get_by_id('u1'))}"}

        response = system.client().post("/auth/change-password", headers=headers,
                                        json={"current_password": GOOD, "new_password": new_password})

        assert response.status_code == 422
        assert response.json()["detail"] == message


def test_valid_password_change_is_accepted(system):
    headers = {"Authorization": f"Bearer {system.auth.create_access_token(system.users.get_by_id('u1'))}"}
    response = system.client().post("/auth/change-password", headers=headers,
                                    json={"current_password": GOOD, "new_password": NEW_VALUE})
    assert response.status_code == 200
    assert login(system.client(), "ana@ejemplo.local", NEW_VALUE).status_code == 200


def test_login_limits_come_from_environment():
    assert get_login_limits({}) == LoginLimits(5, 20, 15)
    assert get_login_limits({"LOGIN_MAX_FAILURES_PER_ACCOUNT": "3", "LOGIN_MAX_FAILURES_PER_IP": "50",
                             "LOGIN_ATTEMPT_WINDOW_MINUTES": "30"}) == LoginLimits(3, 50, 30)
    for bad in ("0", "-1", "cinco"):
        with pytest.raises(ValueError):
            get_login_limits({"LOGIN_MAX_FAILURES_PER_IP": bad})


def test_email_hash_is_normalized():
    assert hash_email(" Ana@Ejemplo.LOCAL ") == hashlib.sha256(b"ana@ejemplo.local").hexdigest()


def test_expired_token_closes_analysis_socket_with_4401_and_cancels_session(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users, students, consents = (PostgresUserRepository(factory), PostgresStudentRepository(factory),
                                 PostgresConsentRepository(factory))
    auth = AuthenticationService(users, JWT_TEST_VALUE)
    identity = IdentityRegistrationService(users, students, consents, auth)
    user, student = identity.register_student("prueba-01@ejemplo.local", GOOD, "PRUEBA-01")
    identity.grant_consent(student.id, "test-v1")
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
    session = sessions.start_session(student_id=student.id, activity_id="arms_up_5s")
    app = FastAPI()
    app.include_router(create_analysis_router(sessions, ActivityCatalog(), auth, users, students,
                                              lambda activity: type("P", (), {"close": lambda self: None})()))
    original = auth.decode_access_token
    calls = {"count": 0}

    def expires_after_connecting(token):
        calls["count"] += 1
        if calls["count"] > 1:
            raise jwt.ExpiredSignatureError("vencido")
        return original(token)

    monkeypatch.setattr(auth, "decode_access_token", expires_after_connecting)
    with TestClient(app).websocket_connect("/ws/activity") as socket:
        socket.send_json({"type": "authenticate", "token": auth.create_access_token(user),
                          "session_id": session.id, "activity_id": "arms_up_5s"})
        assert socket.receive_json()["type"] == "ready"
        socket.send_bytes(b"\xff\xd8frame")
        assert socket.receive_json() == {"type": "error", "message": "Token vencido", "code": 4401}

    assert sessions.get_session(session.id).state is SessionState.CANCELLED
    engine.dispose()


@pytest.mark.parametrize("production", [False, True])
def test_security_headers(production):
    environ = {"ENVIRONMENT": "production" if production else "development",
               "CORS_ORIGINS": "https://emotv.example.org", "TRUSTED_HOSTS": "testserver",
               "DATABASE_URL": "postgresql://emotv@db/emotv", "JWT_SECRET_KEY": JWT_TEST_VALUE}
    app = FastAPI()
    configure_web_security(app, load_web_settings(environ))
    app.get("/ping")(lambda: {"ok": True})

    headers = TestClient(app).get("/ping").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert "camera=(self)" in headers["permissions-policy"]
    assert ("content-security-policy" in headers) is production
