"""El proxy de Vite y el nginx de Docker reenvían a la API todos sus prefijos.

Un prefijo que falta hace que la SPA reciba 404 (o index.html) en vez de la API.
"""
from __future__ import annotations

from pathlib import Path
import re

from emotv.interfaces.web.app import app

ROOT = Path(__file__).resolve().parents[2]


def api_prefixes() -> set[str]:
    return {path.split("/")[1] for path in app.openapi()["paths"]} - {""}


def test_vite_reenvia_todos_los_prefijos_de_la_api():
    config = (ROOT / "web" / "vite.config.ts").read_text(encoding="utf-8")
    block = re.search(r"const apiPrefixes = \[(.*?)\];", config, re.S)
    assert block, "No se encontró apiPrefixes en vite.config.ts"
    proxied = set(re.findall(r'"/([\w-]+)"', block.group(1)))
    assert api_prefixes() - proxied == set()


def test_nginx_reenvia_todos_los_prefijos_de_la_api():
    config = (ROOT / "docker" / "nginx.conf").read_text(encoding="utf-8")
    location = re.search(r"location ~ \^/\(([^)]*)\)\(/\|\$\)", config)
    assert location, "No se encontró la location de la API en nginx.conf"
    assert api_prefixes() - set(location.group(1).split("|")) == set()
