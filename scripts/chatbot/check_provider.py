"""Comprueba que el workflow de Emi responde, sin mostrar secretos.

Hace una o dos llamadas al proveedor configurado en ``.env`` (``CHAT_PROVIDER``)
con preguntas generales, sin datos de nadie, y muestra solo:

- el proveedor y el servidor (sin la ruta, que lleva el id del workflow);
- el resultado (respuesta, o el tipo de fallo y su código HTTP);
- ``in_scope``, la categoría, el tiempo y la respuesta de Emi.

Nunca imprime ``SIM_WORKFLOW_URL`` completa, ``SIM_API_KEY`` ni ``N8N_WEBHOOK_KEY``.
El conocimiento que envía es el texto fijo de ``emi_knowledge`` (sin el catálogo
de expresiones, que está en la base de datos). Cada llamada consume cuota del
modelo de lenguaje.

Uso:
    python scripts/chatbot/check_provider.py            # una pregunta de uso
    python scripts/chatbot/check_provider.py --limites  # además, pide interpretar un dibujo
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
import uuid
from urllib.parse import urlsplit

from emotv.application.emi_knowledge import build_knowledge
from emotv.config import get_activities_enabled, get_chat_settings
from emotv.infrastructure.chat.n8n_client import ChatGatewayError, N8nWebhookChatGateway
from emotv.infrastructure.chat.sim_client import SimChatGateway

QUESTIONS = ("¿Cómo agrego un juego de emparejar a un protocolo?",)
LIMITS = ("Mi alumno dibujó una cara triste, ¿qué significa su dibujo?",)


def host_of(url: str) -> str:
    """Solo el servidor: la ruta lleva el id del workflow."""
    return urlsplit(url).netloc or "(sin configurar)"


def gateway_from_settings():
    settings = get_chat_settings()
    if settings.provider == "sim":
        if not (settings.sim_workflow_url and settings.sim_api_key):
            return None, "sim", host_of(settings.sim_workflow_url)
        return (SimChatGateway(settings.sim_workflow_url, settings.sim_api_key, settings.timeout_seconds),
                "sim", host_of(settings.sim_workflow_url))
    if not settings.webhook_key:
        return None, settings.provider, host_of(settings.webhook_url)
    return (N8nWebhookChatGateway(settings.webhook_url, settings.webhook_key, settings.timeout_seconds),
            settings.provider, host_of(settings.webhook_url))


async def check(questions: tuple[str, ...]) -> int:
    gateway, provider, host = gateway_from_settings()
    print(f"Proveedor: {provider} · servidor: {host}")
    if gateway is None:
        print("Sin configurar: falta la URL o la clave en .env. Emi respondería 503.")
        return 2
    knowledge = build_knowledge((), (), activities_enabled=get_activities_enabled())
    failures = 0
    for question in questions:
        started = time.monotonic()
        try:
            reply = await gateway.ask(str(uuid.uuid4()), question, [], knowledge=knowledge)
        except ChatGatewayError as error:
            failures += 1
            code = f" (HTTP {error.status_code})" if error.status_code else ""
            print(f"\nPregunta: {question}\nNo disponible: {error.kind}{code} en {time.monotonic() - started:.1f} s")
            continue
        print(f"\nPregunta: {question}\nDisponible: in_scope={reply.in_scope} · categoría={reply.category} · "
              f"{time.monotonic() - started:.1f} s\nRespuesta: {reply.answer}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limites", action="store_true", help="también pide interpretar un dibujo")
    args = parser.parse_args()
    return asyncio.run(check(QUESTIONS + (LIMITS if args.limites else ())))


if __name__ == "__main__":
    sys.exit(main())
