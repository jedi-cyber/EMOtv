"""Utilidades compartidas para invocar docker compose desde los scripts."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env.docker"


def add_compose_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env-file", type=Path, default=None,
                        help="Archivo de variables (por defecto .env.docker si existe)")
    parser.add_argument("-f", "--file", dest="files", action="append", type=Path, default=[],
                        help="Archivo compose adicional; repetible (por defecto docker-compose.yml)")


def compose_command(args: argparse.Namespace, *command: str) -> list[str]:
    base = ["docker", "compose", "--project-directory", str(PROJECT_ROOT)]
    env_file = args.env_file or (DEFAULT_ENV_FILE if DEFAULT_ENV_FILE.is_file() else None)
    if env_file is not None:
        base += ["--env-file", str(env_file)]
    for file in args.files:
        base += ["-f", str(file)]
    return base + list(command)


def running_services(args: argparse.Namespace) -> set[str]:
    result = subprocess.run(compose_command(args, "ps", "--status", "running", "--services"),
                            capture_output=True, text=True, check=True)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}
