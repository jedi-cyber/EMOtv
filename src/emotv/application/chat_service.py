"""Emi: conversaciones, límites de uso y filtro de riesgo antes de llamar a n8n.

FastAPI es responsable de la autenticación, los límites, el filtro de riesgo,
el historial y la retención; n8n clasifica el alcance y genera la respuesta.
Al webhook solo llegan la pregunta, el historial de esa conversación dentro de
alcance y ``knowledge``: nunca resultados emocionales, sesiones, nombres,
correos ni el id del usuario.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from emotv.application.chat_safety import RISK_CATEGORY, is_risky
from emotv.application.ports.chat_repository import ChatRepository, StoredChatMessage
from emotv.config import ChatSettings
from emotv.infrastructure.chat.n8n_client import ChatGateway, ChatGatewayError, HistoryMessage

logger = logging.getLogger(__name__)

CURRENT_MESSAGES = 30
UNCATEGORIZED = "sin_categoria"

GATEWAY_ERRORS: dict[str, tuple[int, str]] = {
    "timeout": (504, "Emi tardó demasiado en responder. Intenta de nuevo en unos momentos."),
    "llm_unavailable": (502, "El servicio de inteligencia artificial de Emi no está disponible ahora. "
                             "Intenta de nuevo en unos minutos."),
    "unauthorized": (502, "Emi no está disponible por un problema de configuración del servidor. "
                          "Avisa al responsable de EMOtv."),
    "not_published": (502, "Emi no está disponible: el servicio del asistente no está activo. "
                           "Avisa al responsable de EMOtv."),
    "invalid_response": (502, "Emi devolvió una respuesta que no se pudo leer. Intenta de nuevo."),
    "unavailable": (502, "No se pudo contactar con Emi. Intenta de nuevo en unos minutos."),
}


class ChatError(Exception):
    """Error con el código HTTP y el mensaje en español para el usuario."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True, slots=True)
class ChatAnswer:
    conversation_id: str | None
    answer: str
    in_scope: bool
    category: str
    request_id: str


class ChatService:
    def __init__(
        self,
        repository: ChatRepository,
        gateway: ChatGateway | None,
        settings: ChatSettings,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository
        self.gateway = gateway
        self.settings = settings
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: str(uuid4()))

    def current_conversation(self, user_id: str) -> tuple[str | None, list[StoredChatMessage]]:
        conversation_id = self.repository.latest_conversation(user_id)
        if conversation_id is None:
            return None, []
        return conversation_id, self.repository.list_messages(conversation_id, CURRENT_MESSAGES)

    def new_conversation(self, user_id: str) -> str:
        return self.repository.create_conversation(user_id, self.clock())

    def purge_expired(self) -> int:
        return self.repository.purge(self.clock() - timedelta(days=self.settings.retention_days))

    async def ask(self, user_id: str, question: str, conversation_id: str | None = None) -> ChatAnswer:
        text = question.strip()
        if not text:
            raise ChatError(422, "Escribe una pregunta para Emi.")
        if len(text) > self.settings.max_question_chars:
            raise ChatError(422, f"La pregunta es demasiado larga: usa como máximo "
                                 f"{self.settings.max_question_chars} caracteres.")
        if conversation_id is not None and not self.repository.owns(conversation_id, user_id):
            raise ChatError(404, "Conversación no encontrada")
        now = self.clock()
        self._check_limits(user_id, now)
        request_id = self.id_factory()

        if is_risky(text):
            # No se llama al webhook ni se guarda el texto; solo cuenta la categoría.
            self.repository.record_rejection(RISK_CATEGORY, now)
            logger.info("Emi request_id=%s bloqueada por el filtro de riesgo (sin llamada a n8n)", request_id)
            return ChatAnswer(conversation_id, self.settings.risk_message, False, RISK_CATEGORY, request_id)

        if self.gateway is None:
            raise ChatError(503, "Emi no está disponible: el servidor no tiene configurada la conexión "
                                 "con el asistente.")
        if conversation_id is None:
            conversation_id = (self.repository.latest_conversation(user_id)
                               or self.repository.create_conversation(user_id, now))
        history = [HistoryMessage(message.role, message.content)  # type: ignore[arg-type]
                   for message in self.repository.recent_in_scope(conversation_id,
                                                                   self.settings.history_messages)]
        self.repository.purge(now - timedelta(days=self.settings.retention_days), include_conversations=False)
        message_id = self.repository.add_user_message(conversation_id, text, now)
        try:
            reply = await self.gateway.ask(request_id, text, history, knowledge="")
        except ChatGatewayError as error:
            logger.warning("Emi request_id=%s n8n_status=%s error=%s", request_id,
                           error.status_code if error.status_code is not None else "sin_respuesta", error.kind)
            status, message = GATEWAY_ERRORS.get(error.kind, GATEWAY_ERRORS["unavailable"])
            raise ChatError(status, message) from error
        category = (reply.category.strip().lower()[:64] or UNCATEGORIZED)
        self.repository.complete_exchange(message_id, conversation_id, reply.answer,
                                          reply.in_scope, category, self.clock())
        logger.info("Emi request_id=%s n8n_status=%s in_scope=%s", request_id, reply.status_code, reply.in_scope)
        return ChatAnswer(conversation_id, reply.answer, reply.in_scope, category, request_id)

    def _check_limits(self, user_id: str, now: datetime) -> None:
        settings = self.settings
        recent = self.repository.count_user_messages(user_id, now - timedelta(minutes=settings.window_minutes))
        if recent >= settings.window_messages:
            raise ChatError(429, f"Enviaste muchos mensajes seguidos a Emi. Espera unos minutos: el límite es "
                                 f"{settings.window_messages} mensajes cada {settings.window_minutes} minutos.")
        daily = self.repository.count_user_messages(user_id, now - timedelta(days=1))
        if daily >= settings.daily_messages:
            raise ChatError(429, f"Alcanzaste el límite de {settings.daily_messages} mensajes con Emi en "
                                 f"24 horas. Podrás volver a preguntar más tarde.")
