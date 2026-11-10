"""Guía de uso: los temas del papel de la cuenta que la pide.

El contenido es fijo (``emotv.application.user_guide``) y no incluye datos de
nadie; por eso no se audita."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from emotv.application import AuthenticationService
from emotv.application.ports import UserRepository
from emotv.application.user_guide import guide_for
from emotv.domain import User
from emotv.interfaces.web.auth_router import create_current_user_dependency


def create_guide_router(authentication: AuthenticationService | None, users: UserRepository | None) -> APIRouter:
    router = APIRouter(tags=["guide"])
    current_user = create_current_user_dependency(authentication, users)

    @router.get("/guide")
    def guide(user: User = Depends(current_user)) -> dict[str, Any]:
        return {"topics": [{"id": topic.id, "title": topic.title, "steps": list(topic.steps), "note": topic.note}
                           for topic in guide_for(user.role)]}

    return router
