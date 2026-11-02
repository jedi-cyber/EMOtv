"""Reinicia el segundo factor de una cuenta de gestión (superadmin o admin).

Uso:
    python scripts/security/reset_mfa.py --email admin@ejemplo.local
    docker compose --env-file .env.docker exec api python scripts/security/reset_mfa.py --email admin@ejemplo.local

Para cuando la persona perdió o cambió el celular con la aplicación
autenticadora. Borra la clave TOTP e incrementa token_version (cierra las
sesiones abiertas). En su siguiente ingreso, después de la contraseña, la
cuenta vuelve a configurar la aplicación. No cambia la contraseña: si también
se perdió, usa reset_admin_password.py (superadmin) o pide al superadmin que
restablezca la del admin.

El segundo factor no se reinicia desde la aplicación: con una cuenta robada no
se podría quitar. Igual que reset_admin_password.py, solo funciona si
DATABASE_URL apunta a localhost o a un host de ALLOWED_ADMIN_RESET_HOSTS.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import inspect  # noqa: E402

from emotv.config import get_database_url  # noqa: E402
from emotv.domain import MANAGEMENT_ROLES  # noqa: E402
from emotv.infrastructure.persistence import (  # noqa: E402
    PostgresUserRepository,
    create_database_engine,
    create_session_factory,
)
from scripts.security.reset_admin_password import is_reset_allowed  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="Correo de la cuenta de superadmin o admin")
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
        if user is None or user.role not in MANAGEMENT_ROLES:
            parser.error("No existe una cuenta de superadmin o admin con ese correo")
        users.save(replace(user, mfa_secret=None, mfa_enabled_at=None, mfa_last_step=None,
                           token_version=user.token_version + 1))
    finally:
        engine.dispose()

    print("Segundo factor reiniciado. Las sesiones abiertas quedaron cerradas.")
    print(f"Correo: {user.email}")
    print("En el siguiente ingreso, después de la contraseña, se configurará de nuevo la aplicación autenticadora.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
