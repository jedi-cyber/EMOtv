"""Crea cuentas locales de prueba sin modificar usuarios existentes.

Uso: python scripts/create_demo_role_accounts.py --create
Solo admite PostgreSQL en localhost y muestra las claves generadas una vez.
"""

from __future__ import annotations

import argparse
import secrets

from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from emotv.application import AuthenticationService, IdentityRegistrationService
from emotv.config import get_database_url, get_jwt_secret_key
from emotv.domain import Role
from emotv.infrastructure.persistence import (
    PostgresConsentRepository,
    PostgresStudentRepository,
    PostgresUserRepository,
    create_database_engine,
    create_session_factory,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true", help="Autoriza crear dos cuentas locales de prueba")
    args = parser.parse_args()
    if not args.create:
        parser.error("Indica --create para confirmar la creación de cuentas")

    database_url = get_database_url()
    url = make_url(database_url)
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Este script solo permite una base de datos local")

    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        if not all(inspector.has_table(name) for name in ("users", "students", "consents")):
            parser.error("Faltan tablas de identidad; aplica las migraciones antes de crear cuentas")

        factory = create_session_factory(engine)
        users = PostgresUserRepository(factory)
        students = PostgresStudentRepository(factory)
        consents = PostgresConsentRepository(factory)
        authentication = AuthenticationService(users, get_jwt_secret_key())
        registration = IdentityRegistrationService(users, students, consents, authentication)

        suffix = secrets.token_hex(4)
        psychologist_email = f"psicologo.demo.{suffix}@emotv.local"
        student_email = f"estudiante.demo.{suffix}@emotv.local"
        psychologist_password = secrets.token_urlsafe(18)
        student_password = secrets.token_urlsafe(18)
        student_code = f"DEMO-{suffix.upper()}"

        registration.register_user(psychologist_email, psychologist_password, Role.PSYCHOLOGIST)
        registration.register_student(student_email, student_password, student_code)
        print("Cuentas locales creadas. Guarda estas credenciales ahora; no se almacenan en el repositorio.")
        print(f"Psicología: {psychologist_email} | contraseña: {psychologist_password}")
        print(f"Estudiante: {student_email} | contraseña: {student_password} | código: {student_code}")
        print("No se registró consentimiento para el estudiante.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
