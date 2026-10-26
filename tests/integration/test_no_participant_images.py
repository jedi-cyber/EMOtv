"""Ninguna ruta de la API entrega imágenes de personas evaluadas: las capturas de la
cámara se procesan en memoria y se descartan. La única imagen que sirve la API
es la de un estímulo del banco, subido por un docente o el administrador."""
from __future__ import annotations

import json
import re

from emotv.interfaces.web import app as api_module
from tests.integration.test_protocols_and_stimuli import png_bytes, upload_stimulus
from tests.integration.test_privacy_accounts import env, headers, start_session  # noqa: F401

IMAGE_CONTENT = re.compile(r"^(image/|video/|application/octet-stream)")
# Firmas de imágenes en base64 o como data URI (JPEG, PNG, GIF, WebP).
IMAGE_SIGNATURES = ("data:image", "/9j/", "iVBORw0KGgo", "R0lGOD", "UklGR")
IMAGE_FIELDS = re.compile(r"(image|imagen|frame|cuadro|photo|foto|capture|captura|snapshot|picture|jpeg|png)", re.I)
# Únicas excepciones: la imagen de un estímulo del banco (nunca de una persona evaluada),
# en la web y en el aplicativo móvil (URL firmada; ver tests/integration/test_mobile_api.py).
STIMULUS_FILE = "/stimuli/{stimulus_id}/file"
MOBILE_STIMULUS_FILE = "/mobile/stimulus-images/{session_id}/{stimulus_id}"


def _schemas_with_image_fields(spec: dict) -> list[str]:
    found = []
    for name, schema in spec.get("components", {}).get("schemas", {}).items():
        for field, definition in schema.get("properties", {}).items():
            binary = definition.get("format") in {"binary", "base64"} or definition.get("contentEncoding") == "base64"
            # Una imagen viajaría como texto (base64) o binario; las métricas numéricas
            # como la latencia por cuadro no cuentan.
            textual = definition.get("type") == "string" or any(
                option.get("type") == "string" for option in definition.get("anyOf", []))
            if binary or (textual and IMAGE_FIELDS.search(field)):
                found.append(f"{name}.{field}")
    return found


def test_no_route_declares_images_in_the_real_api():
    spec = api_module.app.openapi()
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            for status, response in operation.get("responses", {}).items():
                for content_type in response.get("content", {}):
                    assert not IMAGE_CONTENT.match(content_type), f"{method.upper()} {path} {status}: {content_type}"
        # Ninguna ruta de consulta se llama como una imagen. La pantalla de la persona
        # sí envía cuadros (POST), pero solo recibe "recibido": se analizan y se descartan.
        if "get" in operations and path != MOBILE_STIMULUS_FILE:
            assert not re.search(r"(capture|captura|frame|photo|foto|snapshot|imagen|image)", path, re.I), path
    assert _schemas_with_image_fields(spec) == []


def test_every_get_route_answers_without_images_for_every_role(env):  # noqa: F811
    session = start_session(env, env.user_1)
    env.client.post(f"/guided-sessions/{session['id']}", headers=headers(env, env.user_1))
    other = start_session(env, env.docente_a, "propia")
    env.client.post(f"/sessions/{other['id']}/cancel", headers=headers(env, env.docente_a))
    certificate = env.client.post(f"/sessions/{other['id']}/delete", headers=headers(env, env.docente_a)).json()
    stimulus = upload_stimulus(env, env.docente_a, png_bytes())
    values = {"session_id": session["id"], "certificate_id": certificate["id"],
              "user_id": env.user_1.id, "student_id": env.student_1.id, "stimulus_id": stimulus["id"]}
    spec = env.client.app.openapi()
    checked = 0
    for path, operations in spec["paths"].items():
        if "get" not in operations:
            continue
        url = re.sub(r"\{(\w+)\}", lambda match: values.get(match.group(1), "x"), path)
        for user in (env.superadmin, env.admin, env.docente_a, env.user_1):
            response = env.client.get(url, headers=headers(env, user))
            content_type = response.headers.get("content-type", "")
            if path == STIMULUS_FILE:
                # Solo el estímulo, y solo para quien puede verlo (docente A y su grupo).
                assert response.status_code == (200 if user in (env.docente_a, env.user_1) else 404), user.role
                checked += 1
                continue
            assert not IMAGE_CONTENT.match(content_type), f"GET {url}: {content_type}"
            body = response.text
            assert not any(signature in body for signature in IMAGE_SIGNATURES), f"GET {url} devolvió una imagen"
            if content_type.startswith("application/json") and response.status_code == 200:
                assert not _json_has_image_fields(json.loads(body)), f"GET {url}"
            checked += 1
    assert checked >= 40  # se recorrieron todas las rutas GET con los cuatro papeles


def _json_has_image_fields(value) -> bool:
    if isinstance(value, dict):
        return any((IMAGE_FIELDS.search(key) and isinstance(item, str) and item) or _json_has_image_fields(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_json_has_image_fields(item) for item in value)
    return False
