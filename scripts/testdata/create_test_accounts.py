"""Crea cuentas de voluntarios PRUEBA-NN para pruebas funcionales.

Uso (desde la raíz, o con docker compose ... exec api):
    python scripts/testdata/create_test_accounts.py --count 3

Cada cuenta es de estudiante, con código PRUEBA-NN consecutivo (continúa desde
el último existente), correo ficticio prueba-NN@emotv.local, contraseña
aleatoria e is_test_account=True. La contraseña se muestra una sola vez en la
terminal y no se guarda en ningún archivo. No acepta nombres ni correos: la
cuenta nunca identifica a la persona. No registra consentimiento: el voluntario
lo acepta en la aplicación. Solo admite PostgreSQL local (o los hosts de
ALLOWED_ADMIN_RESET_HOSTS; en Docker vale "db").
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pwdlib import PasswordHash  # noqa: E402

from scripts.testdata.database import open_database  # noqa: E402
from scripts.testdata.volunteer_data import VolunteerDataError, create_test_accounts  # noqa: E402


def main(argv: list[str] | None = None, *, factory=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--count", type=int, required=True, help="número de cuentas a crear (1-50)")
    args = parser.parse_args(argv)

    with open_database(parser, factory) as session_factory:
        try:
            accounts = create_test_accounts(session_factory, args.count,
                                            hash_password=PasswordHash.recommended().hash)
        except VolunteerDataError as error:
            print(f"No se creó ninguna cuenta: {error}", file=sys.stderr)
            return 1
    print("Cuentas de prueba creadas. Entrega a cada voluntario solo su código y su contraseña.")
    print("Las contraseñas no se guardan en ningún archivo: anótalas ahora.\n")
    for account in accounts:
        print(f"{account.code} | correo: {account.email} | contraseña: {account.password}")
    print("\nNo se registró consentimiento: cada voluntario lo acepta al iniciar sesión.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
