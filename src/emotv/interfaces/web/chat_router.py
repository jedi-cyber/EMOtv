from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from emotv.domain import User
from emotv.infrastructure.chat import FlowiseError
from emotv.interfaces.web.auth_router import create_current_user_dependency


class ChatClient(Protocol):
    async def ask(self, question: str) -> str: ...


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str


def create_chat_router(client: ChatClient | None, authentication=None, users=None) -> APIRouter:
    router = APIRouter(prefix="/chat", tags=["chat"])
    current_user = create_current_user_dependency(authentication, users)

    @router.post("", response_model=ChatResponse)
    async def chat(request: ChatRequest, _: User = Depends(current_user)) -> ChatResponse:
        if client is None:
            raise HTTPException(503, "El chatbot no está configurado")
        question = request.question.strip()
        if not question:
            raise HTTPException(422, "La pregunta no puede estar vacía")
        try:
            return ChatResponse(answer=await client.ask(question))
        except FlowiseError as exc:
            raise HTTPException(502, str(exc)) from exc

    return router
