from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from emotv.application.chat_service import ChatError, ChatService
from emotv.domain import User
from emotv.interfaces.web.auth_router import create_current_user_dependency


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=36)
    # El límite real (CHAT_MAX_QUESTION_CHARS) lo aplica el servicio con un mensaje en español.
    question: str = Field(max_length=20000)


class ChatResponse(BaseModel):
    conversation_id: str | None
    answer: str
    in_scope: bool


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime


class ConversationResponse(BaseModel):
    conversation_id: str | None
    messages: list[ChatMessageResponse]


def create_chat_router(service: ChatService | None, authentication=None, users=None) -> APIRouter:
    router = APIRouter(prefix="/chat", tags=["chat"])
    current_user = create_current_user_dependency(authentication, users)

    def require_service() -> ChatService:
        if service is None:
            raise HTTPException(503, "Emi no está disponible en este servidor")
        return service

    @router.post("", response_model=ChatResponse)
    async def chat(request: ChatRequest, user: User = Depends(current_user)) -> ChatResponse:
        try:
            answer = await require_service().ask(user.id, request.question, request.conversation_id)
        except ChatError as error:
            raise HTTPException(error.status_code, error.message) from error
        return ChatResponse(conversation_id=answer.conversation_id, answer=answer.answer,
                            in_scope=answer.in_scope)

    @router.get("/conversations/current", response_model=ConversationResponse)
    def current(user: User = Depends(current_user)) -> ConversationResponse:
        conversation_id, messages = require_service().current_conversation(user.id)
        return ConversationResponse(conversation_id=conversation_id, messages=[
            ChatMessageResponse(role=item.role, content=item.content, created_at=item.created_at)
            for item in messages
        ])

    @router.post("/conversations", response_model=ConversationResponse, status_code=201)
    def new_conversation(user: User = Depends(current_user)) -> ConversationResponse:
        return ConversationResponse(conversation_id=require_service().new_conversation(user.id), messages=[])

    return router
