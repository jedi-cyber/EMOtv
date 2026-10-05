"""Crea .env.docker a partir de .env.docker.example con secretos aleatorios.

Uso (desde la raíz del repositorio):
    python scripts/docker/init_env.py
Sin Python local:
    docker run --rm -v "${PWD}:/work" -w /work python:3.12-alpine python scripts/docker/init_env.py

Nunca sobrescribe un .env.docker existente. Solo usa la biblioteca estándar.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER = "__GENERATE__"
GENERATORS = {
    # Hexadecimal: seguro dentro de DATABASE_URL sin codificar.
    "POSTGRES_PASSWORD": lambda: secrets.token_hex(24),
    "JWT_SECRET_KEY": lambda: secrets.token_urlsafe(48),
}


def render(template: str) -> str:
    lines = []
    for line in template.splitlines():
        key, separator, value = line.partition("=")
        if separator and value.strip() == PLACEHOLDER and key.strip() in GENERATORS:
            line = f"{key}={GENERATORS[key.strip()]()}"
        lines.append(line)
    rendered = "\n".join(lines) + "\n"
    if PLACEHOLDER in rendered:
        raise ValueError("Quedó un marcador __GENERATE__ sin generador")
    return rendered


def create_env_file(example: Path, target: Path) -> bool:
    """Devuelve False si el destino ya existía y no se tocó."""

    if target.exists():
        return False
    content = render(example.read_text(encoding="utf-8"))
    # "x" falla si otro proceso lo creó entre la comprobación y la escritura.
    with target.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--example", type=Path, default=PROJECT_ROOT / ".env.docker.example")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".env.docker")
    args = parser.parse_args(argv)

    if not create_env_file(args.example, args.output):
        print(f"{args.output.name} ya existe; no se modificó.")
        return 0
    print(f"{args.output.name} creado con POSTGRES_PASSWORD y JWT_SECRET_KEY aleatorios.")
    print("Revisa CORS_ORIGINS, TRUSTED_HOSTS y FLOWISE_API_URL antes de levantar el sistema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
