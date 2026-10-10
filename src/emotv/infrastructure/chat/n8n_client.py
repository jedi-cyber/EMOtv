"""Cliente del workflow EMI publicado en n8n Cloud.

Contrato del webhook (el workflow no se modifica desde este repositorio):

- Petición: ``POST N8N_WEBHOOK_URL`` con la cabecera ``X-EMOtv-Key`` y el cuerpo
  ``{"request_id", "question", "history": [{"role", "content"}], "knowledge"}``.
- 200: ``{"answer": str, "in_scope": bool, "category": str, "request_id": str}``.
- 502: ``{"error": "llm_unavailable", "answer": str, "request_id": str}``.
- 403: la clave no coincide. 404: el workflow no está publicado.

La clave nunca se escribe en logs ni en ``repr``.
"""
from __future__ import annotations

import logging
import os
import ssl
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

logger = logging.getLogger(__name__)

KEY_HEADER = "X-EMOtv-Key"
Role = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True)
class HistoryMessage:
    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class ChatReply:
    answer: str
    in_scope: bool
    category: str
    status_code: int


class ChatGatewayError(RuntimeError):
    """Fallo al consultar el workflow. ``kind`` permite elegir el mensaje al usuario.

    Tipos: ``timeout``, ``llm_unavailable`` (502 de n8n), ``unauthorized``
    (401/403, clave incorrecta), ``not_published`` (404), ``invalid_response``
    y ``unavailable`` (cualquier otro fallo).
    """

    def __init__(self, kind: str, status_code: int | None = None) -> None:
        super().__init__(kind)
        self.kind = kind
        self.status_code = status_code


class ChatGateway(Protocol):
    async def ask(
        self,
        request_id: str,
        question: str,
        history: Sequence[HistoryMessage],
        knowledge: str = "",
    ) -> ChatReply: ...


def _verify_setting(ssl_cert_file: str | None) -> ssl.SSLContext | bool:
    """Usa SSL_CERT_FILE si está definida (redes que interceptan HTTPS)."""
    path = (ssl_cert_file or "").strip()
    if not path:
        return True
    if not os.path.isfile(path):
        logger.warning("SSL_CERT_FILE no apunta a un archivo existente; se usan las CA predeterminadas")
        return True
    return ssl.create_default_context(cafile=path)


class N8nWebhookChatGateway:
    def __init__(
        self,
        url: str,
        key: str,
        timeout_seconds: float = 30.0,
        *,
        ssl_cert_file: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not url.startswith(("https://", "http://")):
            raise ValueError("N8N_WEBHOOK_URL debe ser una URL HTTP o HTTPS")
        if not key:
            raise ValueError("N8N_WEBHOOK_KEY es obligatoria")
        if timeout_seconds <= 0:
            raise ValueError("N8N_TIMEOUT_SECONDS debe ser mayor que cero")
        self.url = url
        self._key = key
        self.timeout_seconds = float(timeout_seconds)
        self._transport = transport
        self._verify = _verify_setting(
            ssl_cert_file if ssl_cert_file is not None else os.environ.get("SSL_CERT_FILE"),
        )

    def __repr__(self) -> str:
        return f"N8nWebhookChatGateway(url={self.url!r}, key=***)"

    async def ask(
        self,
        request_id: str,
        question: str,
        history: Sequence[HistoryMessage],
        knowledge: str = "",
    ) -> ChatReply:
        body = {
            "request_id": request_id,
            "question": question,
            "history": [{"role": item.role, "content": item.content} for item in history],
            "knowledge": knowledge,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, verify=self._verify, transport=self._transport,
            ) as client:
                response = await client.post(self.url, json=body, headers={KEY_HEADER: self._key})
        except httpx.TimeoutException as error:
            raise ChatGatewayError("timeout") from error
        except httpx.HTTPError as error:
            raise ChatGatewayError("unavailable") from error

        status = response.status_code
        if status == 502:
            raise ChatGatewayError("llm_unavailable", status)
        if status in (401, 403):
            raise ChatGatewayError("unauthorized", status)
        if status == 404:
            raise ChatGatewayError("not_published", status)
        if status != 200:
            raise ChatGatewayError("unavailable", status)
        try:
            payload = response.json()
        except ValueError as error:
            raise ChatGatewayError("invalid_response", status) from error
        if not isinstance(payload, dict):
            raise ChatGatewayError("invalid_response", status)
        answer, in_scope = payload.get("answer"), payload.get("in_scope")
        if not isinstance(answer, str) or not answer.strip() or not isinstance(in_scope, bool):
            raise ChatGatewayError("invalid_response", status)
        category = payload.get("category")
        return ChatReply(
            answer=answer.strip(),
            in_scope=in_scope,
            category=category.strip() if isinstance(category, str) else "",
            status_code=status,
        )
