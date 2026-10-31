"""Cliente del workflow de Emi desplegado en Sim (sim.ai) como API.

Contrato (el workflow no se modifica desde este repositorio):

- Petición: ``POST SIM_WORKFLOW_URL`` (``https://www.sim.ai/api/v2/workflows/{id}/execute``)
  con la cabecera ``X-API-Key`` y el cuerpo
  ``{"input": {"request_id", "question", "history": [{"role", "content"}], "knowledge"}}``.
- 200: ``{"data": {"status": "completed", "output": {"answer", "in_scope", "category",
  "request_id"}, "error": null, ...}}``. La salida la fija el bloque Response del
  workflow. Una ejecución con ``status`` ``failed`` también llega con 200.
- 401/403: la clave no es válida o no tiene acceso. 404: el workflow no existe o no
  está desplegado. 402/429: límite de uso de Sim.

Hacia el resto de EMOtv se conserva el contrato de Emi (``ChatReply`` y
``ChatGatewayError``), el mismo que con n8n. La clave nunca se escribe en logs ni en
``repr``.
"""
from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any

import httpx

from emotv.infrastructure.chat.n8n_client import (
    ChatGatewayError,
    ChatReply,
    HistoryMessage,
    _verify_setting,
    parse_reply,
)

SIM_KEY_HEADER = "X-API-Key"
FAILED_RUN_STATES = {"failed", "error", "cancelled", "canceled", "timeout"}


def _output_of(payload: Any, status: int) -> Any:
    """Saca la salida del workflow del sobre de Sim (v2 ``data``; v1 ``success``/``output``)."""
    if not isinstance(payload, dict):
        raise ChatGatewayError("invalid_response", status)
    run = payload["data"] if isinstance(payload.get("data"), dict) else payload
    if run.get("success") is False or str(run.get("status", "")).lower() in FAILED_RUN_STATES:
        raise ChatGatewayError("llm_unavailable", status)
    output = run.get("output", run)
    if isinstance(output, dict) and "answer" not in output:
        # Bloque Response anidado o bloque Agent con salida estructurada en texto.
        if isinstance(output.get("data"), dict):
            output = output["data"]
        elif isinstance(output.get("content"), str):
            try:
                output = json.loads(output["content"])
            except ValueError as error:
                raise ChatGatewayError("invalid_response", status) from error
    if isinstance(output, dict) and output.get("error") == "llm_unavailable":
        raise ChatGatewayError("llm_unavailable", status)
    return output


class SimChatGateway:
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
            raise ValueError("SIM_WORKFLOW_URL debe ser una URL HTTP o HTTPS")
        if not key:
            raise ValueError("SIM_API_KEY es obligatoria")
        if timeout_seconds <= 0:
            raise ValueError("CHAT_TIMEOUT_SECONDS debe ser mayor que cero")
        self.url = url
        self._key = key
        self.timeout_seconds = float(timeout_seconds)
        self._transport = transport
        self._verify = _verify_setting(
            ssl_cert_file if ssl_cert_file is not None else os.environ.get("SSL_CERT_FILE"),
        )

    def __repr__(self) -> str:
        return f"SimChatGateway(url={self.url!r}, key=***)"

    async def ask(
        self,
        request_id: str,
        question: str,
        history: Sequence[HistoryMessage],
        knowledge: str = "",
    ) -> ChatReply:
        body = {"input": {
            "request_id": request_id,
            "question": question,
            "history": [{"role": item.role, "content": item.content} for item in history],
            "knowledge": knowledge,
        }}
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, verify=self._verify, transport=self._transport,
            ) as client:
                response = await client.post(self.url, json=body, headers={SIM_KEY_HEADER: self._key})
        except httpx.TimeoutException as error:
            raise ChatGatewayError("timeout") from error
        except httpx.HTTPError as error:
            raise ChatGatewayError("unavailable") from error

        status = response.status_code
        if status in (401, 403):
            raise ChatGatewayError("unauthorized", status)
        if status == 404:
            raise ChatGatewayError("not_published", status)
        if status in (402, 429):
            raise ChatGatewayError("llm_unavailable", status)
        if status != 200:
            raise ChatGatewayError("unavailable", status)
        try:
            payload = response.json()
        except ValueError as error:
            raise ChatGatewayError("invalid_response", status) from error
        return parse_reply(_output_of(payload, status), status)
