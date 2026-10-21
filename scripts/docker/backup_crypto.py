"""Cifrado de respaldos con BACKUP_KEY (Fernet), distinta de SENSITIVE_DATA_KEY.

Un respaldo contiene toda la base: aunque los campos sensibles ya están cifrados
con SENSITIVE_DATA_KEY, el archivo completo se cifra otra vez con una clave
propia, para que robar un respaldo no baste para leerlo. BACKUP_KEY se lee del
entorno o del archivo --env-file (por defecto .env.docker); nunca se muestra.
Genera una clave con:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from compose_cli import DEFAULT_ENV_FILE

ENCRYPTED_SUFFIX = ".dump.enc"


class BackupKeyError(ValueError):
    """BACKUP_KEY ausente, inválida o igual a la clave de datos sensibles."""


def _env_file_values(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def load_backup_key(args: argparse.Namespace) -> Fernet:
    file_values = _env_file_values(args.env_file or DEFAULT_ENV_FILE)
    key = os.environ.get("BACKUP_KEY", "").strip() or file_values.get("BACKUP_KEY", "")
    if not key:
        raise BackupKeyError("Define BACKUP_KEY (en .env.docker o en el entorno) para cifrar los respaldos")
    sensitive = os.environ.get("SENSITIVE_DATA_KEY", "") or file_values.get("SENSITIVE_DATA_KEY", "")
    if key in {item.strip() for item in sensitive.split(",") if item.strip()}:
        raise BackupKeyError("BACKUP_KEY debe ser distinta de SENSITIVE_DATA_KEY")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as error:
        raise BackupKeyError("BACKUP_KEY no es una clave Fernet válida") from error


def encrypt_backup(fernet: Fernet, data: bytes) -> bytes:
    return fernet.encrypt(data)


def decrypt_backup(fernet: Fernet, data: bytes) -> bytes:
    try:
        return fernet.decrypt(data)
    except InvalidToken as error:
        raise BackupKeyError("No se pudo descifrar el respaldo: BACKUP_KEY no corresponde o el archivo "
                             "está dañado") from error
