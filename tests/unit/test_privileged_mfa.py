"""Segundo factor de superadmin y admin: ingreso en dos pasos, código antes de
cambiar cuentas, bloqueo más estricto, sesiones cortas y reinicio por script."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import AuthenticationService, totp
from emotv.application.audit_service import AuditService
from emotv.application.login_throttle import LoginThrottle
from emotv.application.mfa_service import MfaService
from emotv.config import LoginLimits
from emotv.domain import Role, User
from emotv.infrastructure.persistence import (Base, PostgresConsentRepository, PostgresLoginAttemptRepository,
                                               PostgresStudentRepository, PostgresUserRepository)
from emotv.infrastructure.persistence.models import AccessAuditRecord
from emotv.infrastructure.persistence.postgres_privacy_repositories import PostgresAuditRepository
from emotv.interfaces.web.auth_router import LOGIN_THROTTLED_DETAIL, create_auth_router
from emotv.interfaces.web.identity_router import CONFIRMATION_DETAIL, create_identity_router
from emotv.shared.security.field_encryption import FieldCipher

JWT_TEST_VALUE = "privileged-mfa-test-jwt-value-32-characters"
GOOD = "valor-local-de-gestion-123"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


class System:
    def __init__(self, *, with_cipher: bool = True) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.users = PostgresUserRepository(self.factory)
        self.clock = Clock()
        self.auth = AuthenticationService(self.users, JWT_TEST_VALUE)
        audit = AuditService(PostgresAuditRepository(self.factory))
        cipher = FieldCipher([Fernet.generate_key().decode("ascii")]) if with_cipher else None
        self.mfa = MfaService(self.users, self.auth, cipher, audit, clock=self.clock)
        throttle = LoginThrottle(PostgresLoginAttemptRepository(self.factory),
                                 LoginLimits(max_failures_per_account=5, max_failures_per_ip=20, window_minutes=15),
                                 clock=self.clock)
        app = FastAPI()
        app.include_router(create_auth_router(self.auth, self.users, login_throttle=throttle, mfa=self.mfa))
        app.include_router(create_identity_router(
            self.auth, self.users, PostgresStudentRepository(self.factory), PostgresConsentRepository(self.factory),
            audit=audit, confirm_code=self.mfa.confirm))
        self.client = TestClient(app, client=("10.0.0.1", 50000))
        now = datetime.now(timezone.utc)
        self.admin = self.users.save(User("a1", "admin@ejemplo.local", self.auth.hash_password(GOOD), Role.ADMIN, now))
        self.users.save(User("d1", "docente@ejemplo.local", self.auth.hash_password(GOOD), Role.PSYCHOLOGIST, now))

    def code(self, secret: str, steps_ahead: int = 0) -> str:
        return totp.code_at(secret, totp.time_step(self.clock()) + steps_ahead)

    def password_step(self, password: str = GOOD):
        return self.client.post("/auth/token", data={"username": "admin@ejemplo.local", "password": password})

    def enroll(self) -> tuple[str, str]:
        """Primer ingreso completo: devuelve la clave y el token de acceso."""
        pending = self.password_step().json()["mfa_token"]
        secret = self.client.post("/auth/mfa/setup", json={"mfa_token": pending}).json()["secret"]
        response = self.client.post("/auth/mfa/verify", json={"mfa_token": pending, "code": self.code(secret)})
        assert response.status_code == 200, response.text
        return secret, response.json()["access_token"]

    def audit_actions(self) -> list[tuple[str, str, str]]:
        with self.factory() as db:
            return [(row.action, row.resource_type, row.result) for row in db.scalars(select(AccessAuditRecord))]


@pytest.fixture
def system():
    instance = System()
    yield instance
    instance.engine.dispose()


def test_totp_matches_the_rfc_6238_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # «12345678901234567890» en base32
    assert totp.code_at(secret, 1) == "287082"
    at = datetime.fromtimestamp(59, tz=timezone.utc)
    assert totp.matching_step(secret, "287 082", at) == 1
    assert totp.matching_step(secret, "287082", at, after=1) is None  # ya usado
    assert totp.matching_step(secret, "12345", at) is None


def test_password_alone_gives_no_access_token(system):
    response = system.password_step()
    assert response.status_code == 200
    assert response.json() == {"token_type": "bearer", "mfa": "setup", "mfa_token": response.json()["mfa_token"]}
    pending = response.json()["mfa_token"]
    # El token de paso no sirve como token de acceso.
    assert system.client.get("/auth/me", headers={"Authorization": f"Bearer {pending}"}).status_code == 401


def test_first_login_configures_the_app_and_stores_the_key_encrypted(system):
    pending = system.password_step().json()["mfa_token"]
    first = system.client.post("/auth/mfa/setup", json={"mfa_token": pending}).json()["secret"]
    # Un reintento antes de confirmar entrega la misma clave.
    assert system.client.post("/auth/mfa/setup", json={"mfa_token": pending}).json()["secret"] == first
    secret, access = system.enroll()
    assert secret == first
    stored = system.users.get_by_id("a1")
    assert stored.mfa_enabled and stored.mfa_secret != secret and secret not in stored.mfa_secret
    me = system.client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200 and me.json()["role"] == "admin"
    claims = jwt.decode(access, JWT_TEST_VALUE, algorithms=["HS256"], options={"verify_exp": False})
    assert claims["exp"] - claims["iat"] == 15 * 60
    assert ("update", "mfa", "success") in system.audit_actions()
    assert ("login", "mfa", "success") in system.audit_actions()
    # Una clave confirmada no se vuelve a mostrar.
    pending = system.password_step().json()
    assert pending["mfa"] == "verify"
    assert system.client.post("/auth/mfa/setup", json={"mfa_token": pending["mfa_token"]}).status_code == 409


def test_a_code_is_not_accepted_twice(system):
    secret, _ = system.enroll()
    pending = system.password_step().json()["mfa_token"]
    reused = system.client.post("/auth/mfa/verify", json={"mfa_token": pending, "code": system.code(secret)})
    assert reused.status_code == 401
    assert ("login", "mfa", "failure") in system.audit_actions()
    system.clock.advance(seconds=30)
    fresh = system.client.post("/auth/mfa/verify", json={"mfa_token": pending, "code": system.code(secret)})
    assert fresh.status_code == 200


def test_three_wrong_codes_block_even_the_right_password(system):
    system.enroll()
    system.clock.advance(seconds=1)  # los fallos llegan después del último acceso correcto
    pending = system.password_step().json()["mfa_token"]
    for _ in range(3):
        assert system.client.post("/auth/mfa/verify", json={"mfa_token": pending, "code": "000000"}).status_code in {401, 429}
    blocked = system.password_step()
    assert blocked.status_code == 429 and blocked.json()["detail"] == LOGIN_THROTTLED_DETAIL


def test_three_wrong_passwords_block_a_management_account(system):
    for _ in range(3):
        assert system.password_step("clave-equivocada-1234").status_code == 401
    assert system.password_step().status_code == 429


def test_the_pending_token_expires(system):
    pending = system.password_step().json()["mfa_token"]
    secret = system.client.post("/auth/mfa/setup", json={"mfa_token": pending}).json()["secret"]
    # El token de paso dura 5 minutos según el reloj real del firmado.
    expired = system.auth.create_access_token(system.admin, minutes=-1, claims={"aud": "emotv-mfa"})
    response = system.client.post("/auth/mfa/verify", json={"mfa_token": expired, "code": system.code(secret)})
    assert response.status_code == 401


def test_changing_accounts_requires_the_current_code(system):
    secret, access = system.enroll()
    headers = {"Authorization": f"Bearer {access}"}
    body = {"email": "nuevo@ejemplo.local", "role": "psychologist"}
    without = system.client.post("/users", json=body, headers=headers)
    assert without.status_code == 403 and without.json()["detail"] == CONFIRMATION_DETAIL
    wrong = system.client.post("/users", json=body, headers={**headers, "X-Confirmation-Code": "000000"})
    assert wrong.status_code == 403
    system.clock.advance(seconds=30)
    code = system.code(secret)
    created = system.client.post("/users", json=body, headers={**headers, "X-Confirmation-Code": code})
    assert created.status_code == 201
    # El mismo código confirma varias peticiones seguidas (asignar varios usuarios)...
    again = system.client.post("/users", json={**body, "email": "otro@ejemplo.local"},
                               headers={**headers, "X-Confirmation-Code": code})
    assert again.status_code == 201
    # ...pero no sirve para iniciar sesión.
    pending = system.password_step().json()["mfa_token"]
    assert system.client.post("/auth/mfa/verify", json={"mfa_token": pending, "code": code}).status_code == 401
    reset = system.client.post("/users/d1/reset-password", headers=headers)
    assert reset.status_code == 403
    assert system.users.get_by_id("d1").password_reset_at is None
    # Leer cuentas no pide código.
    assert system.client.get("/users", headers=headers).status_code == 200


def test_management_passwords_need_sixteen_characters(system):
    with pytest.raises(ValueError, match="16 caracteres"):
        system.auth.validate_new_password(system.admin, "quince-caracter")
    docente = system.users.get_by_id("d1")
    system.auth.validate_new_password(docente, "doce-caracte")


def test_other_roles_log_in_with_the_password_only(system):
    response = system.client.post("/auth/token", data={"username": "docente@ejemplo.local", "password": GOOD})
    assert response.status_code == 200 and "mfa" not in response.json()
    claims = jwt.decode(response.json()["access_token"], JWT_TEST_VALUE, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 30 * 60


def test_without_the_encryption_key_management_accounts_cannot_log_in():
    instance = System(with_cipher=False)
    try:
        response = instance.password_step()
        assert response.status_code == 503 and "access_token" not in response.json()
    finally:
        instance.engine.dispose()


def test_without_the_mfa_service_management_accounts_cannot_log_in(system):
    app = FastAPI()
    app.include_router(create_auth_router(system.auth, system.users))
    response = TestClient(app).post("/auth/token", data={"username": "admin@ejemplo.local", "password": GOOD})
    assert response.status_code == 503 and "access_token" not in response.json()


def test_reset_script_clears_the_second_factor(system, tmp_path, monkeypatch):
    from scripts.security import reset_mfa

    url = f"sqlite:///{(tmp_path / 'mfa.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", url)
    users = PostgresUserRepository(sessionmaker(engine, expire_on_commit=False))
    now = datetime.now(timezone.utc)
    users.save(User("s1", "soporte@ejemplo.local", "hash", Role.SUPERADMIN, now, token_version=2,
                    mfa_secret="cifrada", mfa_enabled_at=now, mfa_last_step=10))
    users.save(User("e1", "usuario@ejemplo.local", "hash", Role.STUDENT, now))
    try:
        assert reset_mfa.main(["--email", "SOPORTE@ejemplo.local"]) == 0
        cleared = users.get_by_id("s1")
        assert (cleared.mfa_secret, cleared.mfa_enabled_at, cleared.mfa_last_step) == (None, None, None)
        assert cleared.token_version == 3
        with pytest.raises(SystemExit):
            reset_mfa.main(["--email", "usuario@ejemplo.local"])
    finally:
        engine.dispose()
