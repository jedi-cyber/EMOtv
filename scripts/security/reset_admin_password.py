"""Restablece la contraseña de una cuenta de administración de EMOtv.

Uso:
    python scripts/security/reset_admin_password.py --email admin@ejemplo.local
    docker compose --env-file .env.docker exec api python scripts/security/reset_admin_password.py --email admin@ejemplo.local

Genera una contraseña aleatoria, guarda solo su hash, incrementa
token_version (cierra las sesiones abiertas) y marca must_change_password, de
modo que el primer acceso obliga a cambiarla. La contraseña se muestra una sola
vez en esta terminal. No acepta la contraseña por argumento.

Solo funciona si DATABASE_URL apunta a localhost o a un host listado en
ALLOWED_ADMIN_RESET_HOSTS (separados por comas; en Docker vale "db").
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from emotv.application import AuthenticationService  # noqa: E402
from emotv.config import get_database_url, get_jwt_secret_key  # noqa: E402
from emotv.domain import Role  # noqa: E402
from emotv.infrastructure.persistence import (  # noqa: E402
    PostgresUserRepository,
    create_database_engine,
    create_session_factory,
)

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def allowed_hosts(environ: Mapping[str, str] | None = None) -> frozenset[str]:
    source = os.environ if environ is None else environ
    extra = source.get("ALLOWED_ADMIN_RESET_HOSTS", "")
    return LOCAL_HOSTS | {host.strip() for host in extra.split(",") if host.strip()}


def is_reset_allowed(database_url: str, environ: Mapping[str, str] | None = None) -> bool:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        return True  # archivo local por definición
    return url.host is not None and url.host.lower() in allowed_hosts(environ)


def generate_password() -> str:
    return secrets.token_urlsafe(18)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="Correo de la cuenta de administración")
    args = parser.parse_args(argv)

    database_url = get_database_url()
    if not is_reset_allowed(database_url):
        parser.error("DATABASE_URL no apunta a localhost ni a un host de ALLOWED_ADMIN_RESET_HOSTS")

    engine = create_database_engine(database_url)
    try:
        if not inspect(engine).has_table("users"):
            parser.error("Falta la tabla users; aplica las migraciones (alembic upgrade head)")
        users = PostgresUserRepository(create_session_factory(engine))
        user = users.get_by_email(args.email.strip().lower())
        if user is None or user.role is not Role.ADMIN:
            parser.error("No existe una cuenta de administración con ese correo")
        authentication = AuthenticationService(users, get_jwt_secret_key())
        password = generate_password()
        users.save(replace(
            user,
            password_hash=authentication.hash_password(password),
            must_change_password=True,
            token_version=user.token_version + 1,
        ))
    finally:
        engine.dispose()

    print("Contraseña de administración restablecida. Las sesiones abiertas quedaron cerradas.")
    print(f"Correo: {user.email}")
    print(f"Contraseña temporal: {password}")
    print("Guárdala ahora: no se volverá a mostrar. Se pedirá cambiarla en el primer acceso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
