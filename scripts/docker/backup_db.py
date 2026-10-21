"""Respalda la base de EMOtv con pg_dump dentro del contenedor db.

Uso (desde la raíz del repositorio, Windows o Linux):
    python scripts/docker/backup_db.py
    python scripts/docker/backup_db.py --env-file .env.docker

Guarda backups/emotv-AAAAMMDD-HHMMSS.dump.enc: el volcado de pg_dump (formato
custom) cifrado con BACKUP_KEY, una clave distinta de SENSITIVE_DATA_KEY. Sin
BACKUP_KEY no se guarda nada. El volcado en claro nunca se escribe en disco.
No requiere PostgreSQL instalado en el host. Las credenciales se leen dentro
del contenedor; no pasan por la línea de comandos.

Retención: un respaldo conserva los datos que la aplicación ya eliminó. Elimina
los respaldos con más antigüedad que PARTICIPANT_RETENTION_MONTHS (12 meses por
defecto); los de cuentas de voluntarios, a los 30 días (docs/privacy/).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_cli import PROJECT_ROOT, add_compose_arguments, compose_command, running_services  # noqa: E402
from backup_crypto import ENCRYPTED_SUFFIX, BackupKeyError, encrypt_backup, load_backup_key  # noqa: E402

DUMP_COMMAND = 'pg_dump --format=custom --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_compose_arguments(parser)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "backups")
    args = parser.parse_args(argv)

    try:
        fernet = load_backup_key(args)
    except BackupKeyError as error:
        parser.error(str(error))
    if "db" not in running_services(args):
        parser.error("El servicio db no está en ejecución; levántalo antes de respaldar")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f"emotv-{datetime.now():%Y%m%d-%H%M%S}{ENCRYPTED_SUFFIX}"
    partial = target.with_name(target.name + ".partial")
    # El volcado queda solo en memoria y se escribe ya cifrado.
    result = subprocess.run(compose_command(args, "exec", "-T", "db", "sh", "-c", DUMP_COMMAND),
                            stdout=subprocess.PIPE)
    if result.returncode != 0 or not result.stdout:
        print("pg_dump falló; no se guardó ningún respaldo.", file=sys.stderr)
        return 1
    partial.write_bytes(encrypt_backup(fernet, result.stdout))
    partial.replace(target)
    print(f"Respaldo guardado en {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
