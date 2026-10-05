"""Respalda la base de EMOtv con pg_dump dentro del contenedor db.

Uso (desde la raíz del repositorio, Windows o Linux):
    python scripts/docker/backup_db.py
    python scripts/docker/backup_db.py --env-file .env.docker

Guarda backups/emotv-AAAAMMDD-HHMMSS.dump (formato custom de pg_dump).
No requiere PostgreSQL instalado en el host. Las credenciales se leen dentro
del contenedor; no pasan por la línea de comandos.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compose_cli import PROJECT_ROOT, add_compose_arguments, compose_command, running_services  # noqa: E402

DUMP_COMMAND = 'pg_dump --format=custom --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_compose_arguments(parser)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "backups")
    args = parser.parse_args(argv)

    if "db" not in running_services(args):
        parser.error("El servicio db no está en ejecución; levántalo antes de respaldar")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f"emotv-{datetime.now():%Y%m%d-%H%M%S}.dump"
    partial = target.with_suffix(".dump.partial")
    with partial.open("wb") as handle:
        result = subprocess.run(compose_command(args, "exec", "-T", "db", "sh", "-c", DUMP_COMMAND),
                                stdout=handle)
    if result.returncode != 0 or partial.stat().st_size == 0:
        partial.unlink(missing_ok=True)
        print("pg_dump falló; no se guardó ningún respaldo.", file=sys.stderr)
        return 1
    partial.replace(target)
    print(f"Respaldo guardado en {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
