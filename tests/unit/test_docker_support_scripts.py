from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine

from emotv.infrastructure.persistence import PostgresUserRepository, create_session_factory
from emotv.infrastructure.persistence.models import Base
from scripts import create_demo_role_accounts, download_models
from scripts.docker import init_env
from scripts.security import create_admin

EXAMPLE = (
    "# comentario\n"
    "POSTGRES_USER=emotv\n"
    "POSTGRES_PASSWORD=__GENERATE__\n"
    "DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/emotv\n"
    "JWT_SECRET_KEY=__GENERATE__\n"
)


def _values(content: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in content.splitlines() if "=" in line and not line.startswith("#"))


def test_init_env_generates_random_secrets(tmp_path):
    example, target = tmp_path / "example", tmp_path / ".env.docker"
    example.write_text(EXAMPLE, encoding="utf-8")

    assert init_env.create_env_file(example, target) is True
    first = _values(target.read_text(encoding="utf-8"))
    second = _values(init_env.render(EXAMPLE))

    assert "__GENERATE__" not in target.read_text(encoding="utf-8")
    assert len(first["JWT_SECRET_KEY"]) >= 32
    assert first["POSTGRES_PASSWORD"].isalnum()
    assert first["POSTGRES_PASSWORD"] != second["POSTGRES_PASSWORD"]
    assert first["DATABASE_URL"].startswith("postgresql+psycopg://${POSTGRES_USER}")


def test_init_env_never_overwrites_existing_file(tmp_path):
    example, target = tmp_path / "example", tmp_path / ".env.docker"
    example.write_text(EXAMPLE, encoding="utf-8")
    target.write_text("JWT_SECRET_KEY=keep\n", encoding="utf-8")

    assert init_env.create_env_file(example, target) is False
    assert target.read_text(encoding="utf-8") == "JWT_SECRET_KEY=keep\n"


def test_demo_accounts_reject_remote_hosts_by_default():
    assert "db" not in create_demo_role_accounts.allowed_hosts({})
    assert "localhost" in create_demo_role_accounts.allowed_hosts({})


def test_demo_accounts_accept_listed_hosts():
    hosts = create_demo_role_accounts.allowed_hosts({"ALLOWED_ADMIN_RESET_HOSTS": " db , other "})
    assert {"db", "other", "127.0.0.1"} <= hosts


def test_download_models_detects_hash_mismatch(tmp_path, monkeypatch):
    content = b"pesos de prueba"
    path = tmp_path / "weights" / "model.onnx"
    path.parent.mkdir()
    path.write_bytes(content)
    good = download_models.ModelWeight("x", "https://invalid.example", path, hashlib.sha256(content).hexdigest())
    bad = download_models.ModelWeight("y", "https://invalid.example", path, "0" * 64)

    assert download_models.is_valid(good)
    assert not download_models.is_valid(bad)
    monkeypatch.setattr(download_models, "REQUIRED_WEIGHTS", (good, bad))
    assert download_models.ensure_weights(check_only=True) == ["y"]


def test_download_models_skips_valid_weights_without_network(tmp_path, monkeypatch):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"ok")
    weight = download_models.ModelWeight("x", "https://invalid.example", path, hashlib.sha256(b"ok").hexdigest())
    monkeypatch.setattr(download_models, "REQUIRED_WEIGHTS", (weight,))
    monkeypatch.setattr(download_models, "download", lambda _: pytest.fail("no debe descargar"))

    assert download_models.main([]) == 0


@pytest.fixture
def admin_database(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'emotv.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET_KEY", "isolated-admin-test-secret-at-least-32-chars")
    yield PostgresUserRepository(create_session_factory(engine))
    engine.dispose()


def test_create_admin_stores_only_hash_and_forces_password_change(admin_database, capsys):
    assert create_admin.main(["--email", "Admin@Ejemplo.local"]) == 0
    output = capsys.readouterr().out
    password = next(line.split(": ", 1)[1] for line in output.splitlines() if line.startswith("Contraseña temporal"))

    user = admin_database.get_by_email("admin@ejemplo.local")
    assert user is not None and user.must_change_password and user.role.value == "admin"
    assert password not in user.password_hash
    assert user.password_hash.startswith("$argon2")


def test_create_admin_refuses_second_admin_without_force(admin_database, capsys):
    assert create_admin.main(["--email", "uno@ejemplo.local"]) == 0
    with pytest.raises(SystemExit):
        create_admin.main(["--email", "dos@ejemplo.local"])
    assert admin_database.get_by_email("dos@ejemplo.local") is None

    assert create_admin.main(["--email", "dos@ejemplo.local", "--force"]) == 0
    assert admin_database.get_by_email("dos@ejemplo.local") is not None


def test_create_admin_does_not_accept_password_argument(admin_database):
    with pytest.raises(SystemExit):
        create_admin.main(["--email", "a@ejemplo.local", "--password", "x" * 20])
