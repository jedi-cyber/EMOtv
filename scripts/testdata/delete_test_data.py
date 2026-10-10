"""Elimina cuentas de voluntarios PRUEBA-NN y todos sus registros, con verificación.

Uso (desde la raíz, o con docker compose ... exec api):
    python scripts/testdata/delete_test_data.py --code PRUEBA-07
    python scripts/testdata/delete_test_data.py --expired
    python scripts/testdata/delete_test_data.py --all-test-accounts
    (añade --save para guardar el acta en reports/deletions/)

--code elimina una cuenta (motivo por defecto: solicitud del participante);
--expired, las creadas hace más de TEST_DATA_RETENTION_DAYS días (30 por
defecto); --all-test-accounts, todas, tras escribir ELIMINAR. Solo toca cuentas
con is_test_account=True. Todo ocurre en una transacción: si algo falla o la
verificación encuentra registros restantes, no se borra nada. Al final imprime
el texto del acta de eliminación.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from emotv.config import get_test_data_retention_days  # noqa: E402
from scripts.testdata.database import open_database  # noqa: E402
from scripts.testdata.volunteer_data import (  # noqa: E402
    BACKUP_WARNING,
    DELETIONS_DIR,
    REASON_CLOSING,
    REASON_EXPIRED,
    REASON_REQUEST,
    VolunteerDataError,
    delete_test_data,
    format_report,
    retention_cutoff,
    save_report,
)

CONFIRMATION = "ELIMINAR"
REASONS = {"solicitud": REASON_REQUEST, "expirado": REASON_EXPIRED, "cierre": REASON_CLOSING}


def main(argv: list[str] | None = None, *, factory=None, ask: Callable[[str], str] = input,
         clock: Callable[[], datetime] | None = None, output_dir: Path = DELETIONS_DIR) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--code", help="código de la cuenta, por ejemplo PRUEBA-07")
    mode.add_argument("--expired", action="store_true", help="cuentas con más de TEST_DATA_RETENTION_DAYS días")
    mode.add_argument("--all-test-accounts", action="store_true", help="todas las cuentas de prueba")
    parser.add_argument("--reason", choices=sorted(REASONS), help="motivo del acta (por defecto, según el modo)")
    parser.add_argument("--save", action="store_true", help="guarda el acta en reports/deletions/")
    args = parser.parse_args(argv)

    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if args.code:
        default_reason, options = REASON_REQUEST, {"code": args.code}
    elif args.expired:
        try:
            days = get_test_data_retention_days()
        except ValueError as error:
            parser.error(str(error))
        default_reason, options = REASON_EXPIRED, {"expired_before": retention_cutoff(now, days)}
    else:
        answer = ask(f"Se eliminarán TODAS las cuentas de prueba. Escribe {CONFIRMATION} para confirmar: ")
        if answer.strip() != CONFIRMATION:
            print("Cancelado: no se eliminó nada.")
            return 1
        default_reason, options = REASON_CLOSING, {"all_accounts": True}
    reason = REASONS[args.reason] if args.reason else default_reason

    with open_database(parser, factory) as session_factory:
        try:
            report = delete_test_data(session_factory, reason=reason, clock=lambda: now, **options)
        except VolunteerDataError as error:
            print(f"No se eliminó nada: {error}", file=sys.stderr)
            return 1
    if not report.accounts:
        print("No hay cuentas de prueba que cumplan la condición; no se eliminó nada.")
        return 0

    text = format_report(report)
    print("\n----- Texto para el acta de eliminación -----\n")
    print(text)
    print("\n---------------------------------------------")
    if args.save:
        print(f"Acta guardada en {save_report(text, report.deleted_at, output_dir)}")
    print(f"\n{BACKUP_WARNING}")
    if not report.verified:
        print("La verificación posterior encontró registros: revisa la base antes de firmar el acta.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
