"""Crea la primera cuenta de administración de EMOtv.

Uso:
    python scripts/security/create_admin.py --email admin@ejemplo.local
    docker compose exec api python scripts/security/create_admin.py --email admin@ejemplo.local

La contraseña se genera al ejecutar, se guarda solo su hash argon2 y se muestra
una única vez en esta terminal. La cuenta queda con must_change_password=True,
así que el primer inicio de sesión obliga a cambiarla. No acepta la contraseña
por argumento para que no quede en el historial del shell. Si ya existe un
administrador activo se niega a crear otro salvo con --force.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import inspect  # noqa: E402

from emotv.application import AuthenticationService, IdentityRegistrationService  # noqa: E402
from emotv.config import get_database_url, get_jwt_secret_key  # noqa: E402
from emotv.domain import Role  # noqa: E402
from emotv.infrastructure.persistence import (  # noqa: E402
    PostgresConsentRepository,
    PostgresStudentRepository,
    PostgresUserRepository,
    create_database_engine,
    create_session_factory,
)


def generate_password() -> str:
    return secrets.token_urlsafe(18)


def has_active_admin(users: PostgresUserRepository) -> bool:
    return any(user.role is Role.ADMIN and user.is_active for user in users.list_all())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="Correo de la cuenta de administración")
    parser.add_argument("--force", action="store_true",
                        help="Crear otra cuenta aunque ya exista un administrador activo")
    args = parser.parse_args(argv)

    engine = create_database_engine(get_database_url())
    try:
        if not inspect(engine).has_table("users"):
            parser.error("Falta la tabla users; aplica las migraciones (alembic upgrade head)")
        factory = create_session_factory(engine)
        users = PostgresUserRepository(factory)
        if has_active_admin(users) and not args.force:
            parser.error("Ya existe un administrador activo; usa --force solo si necesitas otro")
        authentication = AuthenticationService(users, get_jwt_secret_key())
        registration = IdentityRegistrationService(
            users, PostgresStudentRepository(factory), PostgresConsentRepository(factory), authentication,
        )
        password = generate_password()
        try:
            user = registration.register_user(args.email, password, Role.ADMIN, must_change_password=True)
        except ValueError as error:
            parser.error(str(error))
    finally:
        engine.dispose()

    print("Cuenta de administración creada.")
    print(f"Correo: {user.email}")
    print(f"Contraseña temporal: {password}")
    print("Guárdala ahora: no se volverá a mostrar. Se pedirá cambiarla en el primer acceso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
