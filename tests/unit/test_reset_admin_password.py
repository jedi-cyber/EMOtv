from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pwdlib import PasswordHash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emotv.domain import Role, User
from emotv.infrastructure.persistence import Base, PostgresUserRepository
from scripts.security import reset_admin_password

JWT_TEST_VALUE = "reset-admin-test-jwt-value-at-least-32-chars"


@pytest.fixture
def users(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'reset.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET_KEY", JWT_TEST_VALUE)
    repository = PostgresUserRepository(sessionmaker(engine, expire_on_commit=False))
    now = datetime.now(timezone.utc)
    hasher = PasswordHash.recommended()
    repository.save(User("admin-1", "admin@ejemplo.local", hasher.hash("old-local-value-123"), Role.ADMIN, now,
                         token_version=3))
    repository.save(User("student-1", "student@ejemplo.local", hasher.hash("old-local-value-456"), Role.STUDENT, now))
    yield repository
    engine.dispose()


def temporary_password(output: str) -> str:
    return next(line.split(": ", 1)[1] for line in output.splitlines() if line.startswith("Contraseña temporal"))


def test_reset_rotates_password_invalidates_sessions_and_forces_change(users, capsys):
    assert reset_admin_password.main(["--email", "ADMIN@ejemplo.local"]) == 0

    password = temporary_password(capsys.readouterr().out)
    admin = users.get_by_email("admin@ejemplo.local")
    hasher = PasswordHash.recommended()
    assert len(password) >= 24
    assert hasher.verify(password, admin.password_hash)
    assert not hasher.verify("old-local-value-123", admin.password_hash)
    assert password not in admin.password_hash
    assert admin.must_change_password is True
    assert admin.token_version == 4


def test_each_reset_generates_a_different_password(users, capsys):
    reset_admin_password.main(["--email", "admin@ejemplo.local"])
    first = temporary_password(capsys.readouterr().out)
    reset_admin_password.main(["--email", "admin@ejemplo.local"])
    assert temporary_password(capsys.readouterr().out) != first


@pytest.mark.parametrize("email", ["student@ejemplo.local", "nadie@ejemplo.local"])
def test_refuses_non_admin_or_unknown_accounts(users, email):
    with pytest.raises(SystemExit) as error:
        reset_admin_password.main(["--email", email])
    assert error.value.code == 2
    assert users.get_by_email("student@ejemplo.local").token_version == 0


def test_password_cannot_be_given_as_argument(users):
    with pytest.raises(SystemExit):
        reset_admin_password.main(["--email", "admin@ejemplo.local", "--password", "x"])


def test_refuses_remote_database_before_connecting(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://emotv@db.produccion.example.org:5432/emotv")
    monkeypatch.delenv("ALLOWED_ADMIN_RESET_HOSTS", raising=False)
    with pytest.raises(SystemExit) as error:
        reset_admin_password.main(["--email", "admin@ejemplo.local"])
    assert error.value.code == 2
    assert "ALLOWED_ADMIN_RESET_HOSTS" in capsys.readouterr().err


@pytest.mark.parametrize(("url", "extra", "allowed"), [
    ("postgresql://emotv@localhost/emotv", "", True),
    ("postgresql://emotv@127.0.0.1:5433/emotv", "", True),
    ("postgresql://emotv@db:5432/emotv", "", False),
    ("postgresql://emotv@db:5432/emotv", "db", True),
    ("postgresql://emotv@db.example.org/emotv", "db, otro", False),
    ("sqlite:///local.db", "", True),
])
def test_host_guard(url, extra, allowed):
    assert reset_admin_password.is_reset_allowed(url, {"ALLOWED_ADMIN_RESET_HOSTS": extra}) is allowed
