"""Restaura un respaldo de EMOtv REEMPLAZANDO la base actual.

Uso (desde la raíz del repositorio, Windows o Linux):
    python scripts/docker/restore_db.py backups/emotv-20261005-120000.dump.enc

Pide escribir RESTAURAR para continuar. Detiene la API mientras restaura (si
estaba en ejecución) y la vuelve a iniciar al terminar. Usa pg_restore dentro
del contenedor db; no requiere PostgreSQL instalado en el host. Los respaldos
.dump.enc se descifran en memoria con BACKUP_KEY; el volcado en claro nunca se
escribe en disco.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_cli import add_compose_arguments, compose_command, running_services  # noqa: E402
from backup_crypto import ENCRYPTED_SUFFIX, BackupKeyError, decrypt_backup, load_backup_key  # noqa: E402

CONFIRMATION = "RESTAURAR"
RESTORE_COMMAND = (
    'pg_restore --clean --if-exists --no-owner --single-transaction '
    '-U "$POSTGRES_USER" -d "$POSTGRES_DB"'
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_compose_arguments(parser)
    parser.add_argument("backup", type=Path, help="Archivo .dump.enc creado por backup_db.py")
    args = parser.parse_args(argv)

    if not args.backup.is_file():
        parser.error(f"No existe el respaldo: {args.backup}")
    if not args.backup.name.endswith(ENCRYPTED_SUFFIX):
        parser.error("Solo se restauran respaldos cifrados (.dump.enc) creados por backup_db.py")
    try:
        dump = decrypt_backup(load_backup_key(args), args.backup.read_bytes())
    except BackupKeyError as error:
        parser.error(str(error))
    services = running_services(args)
    if "db" not in services:
        parser.error("El servicio db no está en ejecución; levántalo antes de restaurar")

    print(f"Se reemplazará TODA la base actual con {args.backup.name}.")
    if input(f"Escribe {CONFIRMATION} para continuar: ").strip() != CONFIRMATION:
        print("Cancelado; no se modificó nada.")
        return 1

    api_was_running = "api" in services
    if api_was_running:
        subprocess.run(compose_command(args, "stop", "api"), check=True)
    try:
        result = subprocess.run(compose_command(args, "exec", "-T", "db", "sh", "-c", RESTORE_COMMAND),
                                input=dump)
    finally:
        if api_was_running:
            subprocess.run(compose_command(args, "start", "api"), check=False)
    if result.returncode != 0:
        print("pg_restore falló; la transacción se revirtió.", file=sys.stderr)
        return 1
    print("Restauración completada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
