from __future__ import annotations

from typing import Any

import httpx


class FlowiseError(RuntimeError):
    """Error seguro para fallos de comunicación o respuestas de Flowise."""


class FlowiseClient:
    def __init__(self, api_url: str, api_key: str | None = None, timeout_seconds: float = 20) -> None:
        if not api_url.startswith(("https://", "http://")):
            raise ValueError("FLOWISE_API_URL debe ser una URL HTTP o HTTPS")
        if timeout_seconds <= 0:
            raise ValueError("FLOWISE_TIMEOUT_SECONDS debe ser mayor que cero")
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def ask(self, question: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.api_url, json={"question": question}, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FlowiseError("El asistente no está disponible en este momento") from exc
        answer = self._extract_answer(payload)
        if not answer:
            raise FlowiseError("Flowise devolvió una respuesta vacía")
        return answer

    @staticmethod
    def _extract_answer(payload: Any) -> str:
        if isinstance(payload, str):
            return payload.strip()
        if not isinstance(payload, dict):
            return ""
        for key in ("text", "answer", "response", "output"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
