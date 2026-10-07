"""Detector de secretos sobre repositorios Git temporales."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.security import check_secrets

ROOT = Path(__file__).resolve().parents[2]
# Se arman por partes para que este archivo no active el detector.
FAKE_VALUE = "Xk29" + "ajd82kdlqP"
LEAK_LINE = "pass" + f'word = "{FAKE_VALUE}"\n'

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requiere git")


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=Prueba", "-c", "user.email=prueba@example.org",
                           "-c", "commit.gpgsign=false", *args], capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    path = tmp_path / "repo"
    path.mkdir()
    assert run_git(path, "init", "-q").returncode == 0
    monkeypatch.chdir(path)
    return path


def stage(repo: Path, name: str, content: str | bytes) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content, encoding="utf-8", newline="\n")
    assert run_git(repo, "add", name).returncode == 0


def test_detects_staged_secret_and_masks_value(repo, capsys):
    stage(repo, "app/config.py", "x = 1\n" + LEAK_LINE)

    assert check_secrets.main([]) == 1
    output = capsys.readouterr().out
    assert "app/config.py:2: credencial-literal (valor: Xk2***)" in output
    assert FAKE_VALUE not in output


@pytest.mark.parametrize(("name", "content", "rule"), [
    ("db.py", "URL = 'postgresql://emotv:" + "Kq83nd02mzP@db:5432/emotv'\n", "url-con-credenciales"),
    ("chat.py", "KEY = load('gsk_" + "a" * 4 + "Zx81mQ0pLk29dJ4nB7vT')\n", "clave-groq"),
    ("id_rsa.txt", "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIE\n", "clave-privada-pem"),
    (".env", "JWT_SECRET_" + "KEY=Gq8xP2mZ7vR4tL9wK3nB6cY1hJ5sD0fA\n", "variable-secreta-env"),
    (".env.production", "FLOWISE_API_" + "KEY=fw_Lk29dJ4nB7vT0pQ\n", "variable-secreta-env"),
    ("check.py", "auth.authenticate(\n    'admin@example.org',\n    'Mz8" + "qL2vX0pK',\n)\n", "clave-en-llamada-de-login"),
    (".tmp_check.py", "print('hola')\n", "archivo-temporal-versionado"),
])
def test_detects_each_rule(repo, capsys, name, content, rule):
    stage(repo, name, content)

    assert check_secrets.main([]) == 1
    assert f": {rule} " in capsys.readouterr().out


def test_login_call_rule_needs_a_literal_after_a_literal_email(repo, capsys):
    stage(repo, "test_login.py", "login(client, 'ana@example.org', BAD_VALUE)\n"
                                 "login(client, 'ana@example.org', 'Mz8" + "qL2vX0pK')\n")

    assert check_secrets.main([]) == 1
    output = capsys.readouterr().out
    assert "test_login.py:2: clave-en-llamada-de-login" in output
    assert "test_login.py:1:" not in output


@pytest.mark.parametrize("content", [
    "JWT_SECRET_" + "KEY=replace-with-at-least-32-random-characters\nPOSTGRES_PASSWORD=__GENERATE__\n"
    "DATABASE_URL=postgresql+psycopg://emotv:change-me@localhost:5432/emotv\n# FLOWISE_API_KEY=\n",
    "DATABASE_URL=postgresql://usuario:clave@localhost/emotv\nFLOWISE_API_KEY=<tu-clave>\n",
])
def test_placeholders_in_env_example_are_ignored(repo, capsys, content):
    stage(repo, ".env.example", content)

    assert check_secrets.main([]) == 0
    assert "sin hallazgos" in capsys.readouterr().out


def test_allowlist_matches_path_and_pattern(repo, capsys):
    stage(repo, "tests/test_login.py", "def test():\n    " + LEAK_LINE)
    assert check_secrets.main([]) == 1

    stage(repo, ".secrets-allowlist", "# datos ficticios\nother/*.py:Xk29\ntests/*.py:Xk29ajd\n")
    assert check_secrets.main([]) == 0
    capsys.readouterr()

    stage(repo, ".secrets-allowlist", "tests/*.py:otro-patron\n")
    assert check_secrets.main([]) == 1


def test_utf16_allowlist_from_powershell_is_read_without_exit_2(repo):
    stage(repo, "tests/test_login.py", LEAK_LINE)
    stage(repo, ".secrets-allowlist", "tests/*.py:Xk29\r\n".encode("utf-16"))

    assert check_secrets.main([]) == 0


def test_binary_and_non_utf8_files_are_skipped_without_exit_2(repo, capsys):
    stage(repo, "image.png", b"\x89PNG\x00\x00" + LEAK_LINE.encode())
    stage(repo, "legacy.txt", "contraseña\n".encode("latin-1") + LEAK_LINE.encode())

    assert check_secrets.main([]) == 0
    warnings = capsys.readouterr().err
    assert "image.png: omitido, archivo binario" in warnings
    assert "legacy.txt: omitido, no está codificado en UTF-8" in warnings


def test_default_mode_scans_only_staged_files_and_all_scans_tracked(repo):
    stage(repo, "old.py", LEAK_LINE)
    assert run_git(repo, "commit", "-q", "-m", "inicial", "--no-verify").returncode == 0
    (repo / "untracked.py").write_text(LEAK_LINE, encoding="utf-8")
    stage(repo, "clean.py", "x = 1\n")

    assert check_secrets.main([]) == 0
    assert check_secrets.main(["--all"]) == 1


def test_scans_staged_content_not_working_tree(repo):
    stage(repo, "app.py", LEAK_LINE)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")

    assert check_secrets.main([]) == 1


def test_outside_repository_blocks_with_exit_1(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert check_secrets.main(["--all"]) == 1
    assert "se bloquea por seguridad" in capsys.readouterr().err


def test_project_repository_is_clean():
    if run_git(ROOT, "rev-parse", "--is-inside-work-tree").returncode != 0:
        pytest.skip("no es un repositorio Git")
    result = subprocess.run(["python" if shutil.which("python") else "python3",
                             "scripts/security/check_secrets.py", "--all"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def install_hook(repo: Path) -> None:
    (repo / ".githooks").mkdir()
    shutil.copy(ROOT / ".githooks" / "pre-commit", repo / ".githooks" / "pre-commit")
    (repo / ".githooks" / "pre-commit").chmod(0o755)
    (repo / "scripts" / "security").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "security" / "check_secrets.py", repo / "scripts" / "security")
    assert run_git(repo, "config", "core.hooksPath", ".githooks").returncode == 0


needs_posix_hook = pytest.mark.skipif(
    shutil.which("sh") is None or shutil.which("python3") is None or sys.platform == "win32",
    reason="requiere sh y python3 de POSIX")


@needs_posix_hook
def test_pre_commit_hook_accepts_python_that_prints_crlf(repo):
    """Python en Windows escribe "ok\\r\\n"; el hook no debe descartarlo."""
    install_hook(repo)
    marker = repo / "venv-used"
    fake = repo / ".venv" / "bin" / "python"
    fake.parent.mkdir(parents=True)
    fake.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-\" ]; then cat >/dev/null; printf 'ok\\r\\n'; exit 0; fi\n"
        f"touch '{marker}'\n"
        "exec python3 \"$@\"\n", encoding="utf-8", newline="\n")
    fake.chmod(0o755)

    stage(repo, "leak.py", LEAK_LINE)
    blocked = run_git(repo, "commit", "-q", "-m", "con secreto")

    assert marker.exists(), blocked.stderr
    assert blocked.returncode != 0
    assert "leak.py:1: credencial-literal" in blocked.stdout + blocked.stderr


@needs_posix_hook
def test_pre_commit_hook_blocks_secret(repo):
    install_hook(repo)

    stage(repo, "ok.py", "x = 1\n")
    assert run_git(repo, "commit", "-q", "-m", "limpio").returncode == 0

    stage(repo, "leak.py", LEAK_LINE)
    blocked = run_git(repo, "commit", "-q", "-m", "con secreto")
    assert blocked.returncode != 0
    assert "leak.py:1: credencial-literal" in blocked.stdout + blocked.stderr
    assert FAKE_VALUE not in blocked.stdout + blocked.stderr
