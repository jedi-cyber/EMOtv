"""Respaldos cifrados con BACKUP_KEY, distinta de SENSITIVE_DATA_KEY."""
from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "docker"))
import backup_crypto  # noqa: E402
import backup_db  # noqa: E402


def args(env_file: Path) -> Namespace:
    return Namespace(env_file=env_file, files=[])


def test_backup_roundtrip_and_wrong_key(tmp_path, monkeypatch):
    monkeypatch.delenv("BACKUP_KEY", raising=False)
    monkeypatch.delenv("SENSITIVE_DATA_KEY", raising=False)
    key = Fernet.generate_key().decode()
    env_file = tmp_path / ".env.docker"
    env_file.write_text(f"BACKUP_KEY={key}\nSENSITIVE_DATA_KEY={Fernet.generate_key().decode()}\n", encoding="utf-8")
    fernet = backup_crypto.load_backup_key(args(env_file))
    encrypted = backup_crypto.encrypt_backup(fernet, b"PGDMP volcado")
    assert b"PGDMP" not in encrypted
    assert backup_crypto.decrypt_backup(fernet, encrypted) == b"PGDMP volcado"
    with pytest.raises(backup_crypto.BackupKeyError):
        backup_crypto.decrypt_backup(Fernet(Fernet.generate_key()), encrypted)


@pytest.mark.parametrize("content", ["", "BACKUP_KEY=no-es-una-clave\n", "SAME"])
def test_backup_key_is_required_valid_and_different(tmp_path, monkeypatch, content):
    monkeypatch.delenv("BACKUP_KEY", raising=False)
    monkeypatch.delenv("SENSITIVE_DATA_KEY", raising=False)
    if content == "SAME":
        key = Fernet.generate_key().decode()
        content = f"BACKUP_KEY={key}\nSENSITIVE_DATA_KEY=otra,{key}\n"
    env_file = tmp_path / ".env.docker"
    env_file.write_text(content, encoding="utf-8")
    with pytest.raises(backup_crypto.BackupKeyError):
        backup_crypto.load_backup_key(args(env_file))


def test_backup_script_refuses_to_run_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("BACKUP_KEY", raising=False)
    env_file = tmp_path / ".env.docker"
    env_file.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit):
        backup_db.main(["--env-file", str(env_file), "--output-dir", str(tmp_path / "backups")])
    assert not (tmp_path / "backups").exists()
