"""Detector de credenciales para EMOtv, sin dependencias externas.

Uso (desde cualquier carpeta del repositorio):
    python scripts/security/check_secrets.py          # archivos en staging
    python scripts/security/check_secrets.py --all    # todos los archivos versionados

Lee el contenido desde el índice de Git, es decir, exactamente lo que se va a
confirmar. Reglas: asignaciones a password/passwd/secret/api_key/token con un
literal de 12+ caracteres, URLs con usuario y clave, claves de Groq (gsk_),
claves privadas PEM, valores reales de variables secretas en archivos .env
versionados, contraseñas literales pasadas a authenticate()/login() en Python
y scripts temporales (.tmp_*) versionados.

Ignora valores de ejemplo (change-me, replace-with-..., __GENERATE__, <...>) y
los hallazgos cubiertos por .secrets-allowlist, con una entrada por línea en
formato ``ruta:patrón``: la ruta admite comodines (``tests/*``) y el patrón es
una expresión regular que se busca en la línea del hallazgo.

Códigos de salida: 0 sin hallazgos, 1 con hallazgos o si Git no responde (se
bloquea por seguridad). Los archivos binarios o que no son UTF-8 se omiten con
un aviso; nunca se devuelve 2 por un error de lectura. Los valores se muestran
enmascarados (``abc***``), nunca completos.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath

ALLOWLIST_PATH = ".secrets-allowlist"
MAX_BYTES = 5 * 1024 * 1024
SECRET_WORDS = "(?:" + "|".join(("password", "passwd", "secret", r"api[_-]?key", "token")) + ")"

ASSIGNMENT = re.compile(
    rf"""(?ix)
    \b[\w.-]*{SECRET_WORDS}[\w-]*["']?   # nombre de la clave
    \s*(?::|=|:=|=>)\s*                  # asignación o par clave-valor
    [rbuf]{{0,2}}(["'])(?P<value>[^"'\r\n]{{12,}})\1
    """
)
URL_CREDENTIALS = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@'\"]+:(?P<value>[^\s/@'\"]+)@", re.I)
GROQ_KEY = re.compile(r"\b(?P<value>gsk_[A-Za-z0-9]{20,})")
PRIVATE_KEY = re.compile(r"(?P<value>-----BEGIN (?:[A-Z]+ )*PRIVATE KEY(?: BLOCK)?-----)")
ENV_SECRET = re.compile(
    rf"(?i)^\s*(?:export\s+)?(?P<key>[A-Z0-9_]*{SECRET_WORDS}[A-Z0-9_]*)\s*=\s*(?P<value>.*?)\s*$"
)

LOGIN_CALLS = {"authenticate", "login", "log_in", "check_login", "sign_in"}
# Scripts temporales como el .tmp_check_login.py que expuso una contraseña.
TEMPORARY_PREFIXES = (".tmp_", ".tmp-")

PLACEHOLDER_MARKERS = (
    "change-me", "changeme", "change_me", "replace-with", "replace_with", "replace-me",
    "your-", "your_", "example", "placeholder", "dummy", "redacted", "__generate__",
    "xxx", "***", "<", ">", "${", "{{",
)
PLACEHOLDER_WORDS = {"secret", "password", "passwd", "token", "changeit", "test", "none", "null", "true", "false",
                     "clave", "contraseña", "contrasena", "usuario"}


@dataclass(frozen=True)
class Finding:
    path: str
    line_number: int
    rule: str
    value: str
    line: str

    def report(self) -> str:
        return f"{self.path}:{self.line_number}: {self.rule} (valor: {mask(self.value)})"


@dataclass(frozen=True)
class AllowRule:
    path: str
    pattern: re.Pattern[str]

    def covers(self, finding: Finding) -> bool:
        return fnmatch.fnmatchcase(finding.path, self.path) and self.pattern.search(finding.line) is not None


class GitError(RuntimeError):
    pass


def mask(value: str) -> str:
    return value[:3] + "***"


def is_placeholder(value: str) -> bool:
    cleaned = value.strip().strip("\"'")
    lowered = cleaned.lower()
    if not cleaned or cleaned.startswith("$") or lowered in PLACEHOLDER_WORDS:
        return True
    if len(set(cleaned)) <= 2:  # ********, xxxxxxxx, 00000000
        return True
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def is_env_file(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return name == ".env" or name.startswith(".env.") or name.endswith(".env")


def login_call_literals(text: str) -> list[tuple[int, str]]:
    """Contraseñas literales que siguen a un correo literal en authenticate()/login().

    Cubre el caso de .tmp_check_login.py, donde la clave no tenía un nombre
    de variable delante y las reglas por línea no la veían. Exigir el correo
    justo antes evita confundir el propio correo con la contraseña en
    llamadas como login(client, "correo", clave).
    """

    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return []
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", "")
        if name.lower() not in LOGIN_CALLS:
            continue
        for email, argument in zip(node.args, node.args[1:]):
            if (_string(email) and "@" in email.value and _string(argument)
                    and len(argument.value) >= 8 and not is_placeholder(argument.value)):
                found.append((argument.lineno, argument.value))
    return found


def _string(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    name = PurePosixPath(path).name
    if name.startswith(TEMPORARY_PREFIXES):
        findings.append(Finding(path, 1, "archivo-temporal-versionado", name, lines[0] if lines else ""))
    if path.endswith(".py"):
        for number, value in login_call_literals(text):
            findings.append(Finding(path, number, "clave-en-llamada-de-login", value, lines[number - 1]))
    env_file = is_env_file(path)
    for number, line in enumerate(lines, start=1):
        seen: set[str] = set()

        def add(rule: str, value: str) -> None:
            if rule not in seen:
                seen.add(rule)
                findings.append(Finding(path, number, rule, value, line))

        for match in ASSIGNMENT.finditer(line):
            if not is_placeholder(match["value"]):
                add("credencial-literal", match["value"])
        for match in URL_CREDENTIALS.finditer(line):
            if not is_placeholder(match["value"]):
                add("url-con-credenciales", match["value"])
        for match in GROQ_KEY.finditer(line):
            add("clave-groq", match["value"])
        if (match := PRIVATE_KEY.search(line)) is not None:
            add("clave-privada-pem", match["value"])
        if env_file and (match := ENV_SECRET.match(line)) is not None:
            value = match["value"].split(" #", 1)[0].strip().strip("\"'")
            if not is_placeholder(value):
                add("variable-secreta-env", value)
    return findings


def decode(path: str, data: bytes) -> str | None:
    """Devuelve el texto o None si el archivo debe omitirse (con aviso)."""

    if len(data) > MAX_BYTES:
        warn(f"{path}: omitido, supera {MAX_BYTES // (1024 * 1024)} MiB")
        return None
    if b"\x00" in data[:8192]:
        warn(f"{path}: omitido, archivo binario")
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        warn(f"{path}: omitido, no está codificado en UTF-8")
        return None


def parse_allowlist(data: bytes | None) -> list[AllowRule]:
    if not data:
        return []
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16", errors="replace")  # típico de '>' en PowerShell 5.1
    else:
        text = data.decode("utf-8-sig", errors="replace")
    rules: list[AllowRule] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        path, separator, pattern = entry.partition(":")
        if not separator or not path.strip() or not pattern.strip():
            warn(f"{ALLOWLIST_PATH}:{number}: entrada ignorada, el formato es ruta:patrón")
            continue
        try:
            rules.append(AllowRule(path.strip(), re.compile(pattern.strip())))
        except re.error:
            warn(f"{ALLOWLIST_PATH}:{number}: entrada ignorada, patrón no válido")
    return rules


def git(*args: str, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(["git", *args], input=input_bytes, capture_output=True, check=False)
    except OSError as error:
        raise GitError("No se pudo ejecutar git") from error
    if result.returncode != 0:
        raise GitError(f"git {args[0]} falló")
    return result.stdout


def index_entries() -> dict[str, str]:
    """Ruta -> id del blob en el índice (omite submódulos y enlaces)."""

    entries: dict[str, str] = {}
    for record in git("ls-files", "-s", "-z").split(b"\x00"):
        if not record:
            continue
        meta, _, raw_path = record.partition(b"\t")
        mode, blob, _stage = meta.decode("ascii").split()
        if mode in {"100644", "100755"}:
            entries[raw_path.decode("utf-8", errors="surrogateescape")] = blob
    return entries


def staged_paths() -> set[str]:
    output = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    return {raw.decode("utf-8", errors="surrogateescape") for raw in output.split(b"\x00") if raw}


def read_blobs(blob_ids: list[str]) -> list[bytes | None]:
    """Lee varios blobs con una sola llamada a ``git cat-file --batch``."""

    if not blob_ids:
        return []
    output = git("cat-file", "--batch", input_bytes="".join(f"{blob}\n" for blob in blob_ids).encode("ascii"))
    contents: list[bytes | None] = []
    position = 0
    for _ in blob_ids:
        header_end = output.index(b"\n", position)
        header = output[position:header_end].split()
        if len(header) < 3 or header[1] != b"blob":
            contents.append(None)
            position = header_end + 1
            continue
        size = int(header[2])
        start = header_end + 1
        contents.append(output[start:start + size])
        position = start + size + 1
    return contents


def check(all_files: bool) -> tuple[list[Finding], int]:
    entries = index_entries()
    paths = sorted(entries if all_files else staged_paths() & entries.keys())
    allow_data = read_blobs([entries[ALLOWLIST_PATH]])[0] if ALLOWLIST_PATH in entries else None
    allow_rules = parse_allowlist(allow_data)
    findings: list[Finding] = []
    for path, data in zip(paths, read_blobs([entries[path] for path in paths])):
        if data is None:
            warn(f"{path}: omitido, no se pudo leer del índice")
            continue
        text = decode(path, data)
        if text is None:
            continue
        findings.extend(item for item in scan_text(path, text)
                        if not any(rule.covers(item) for rule in allow_rules))
    return findings, len(paths)


def warn(message: str) -> None:
    print(f"aviso: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="Revisar todos los archivos versionados")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        # Una consola con otra página de códigos no debe hacer fallar el detector.
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    try:
        findings, scanned = check(args.all)
    except GitError as error:
        print(f"Detector de secretos: {error}; se bloquea por seguridad.", file=sys.stderr)
        return 1
    for finding in findings:
        print(finding.report())
    scope = "versionados" if args.all else "en staging"
    if findings:
        print(f"Detector de secretos: {len(findings)} hallazgo(s) en {scanned} archivo(s) {scope}.")
        print("Quita la credencial (usa variables de entorno) o, si es un dato de prueba, "
              f"agrega una entrada ruta:patrón a {ALLOWLIST_PATH}.")
        return 1
    print(f"Detector de secretos: sin hallazgos en {scanned} archivo(s) {scope}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
