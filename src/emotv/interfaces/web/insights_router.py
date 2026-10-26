"""Línea de tiempo y métricas por estímulo de una sesión.

Describen lo registrado; no interpretan. Cada consulta se audita.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from emotv.application import AuthenticationService
from emotv.application.ports import UserRepository
from emotv.application.session_insights_service import InsightsNotFound, SessionInsightsService
from emotv.domain import User
from emotv.interfaces.web.auth_router import create_current_user_dependency


def create_insights_router(
    insights: SessionInsightsService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["insights"])
    current_user = create_current_user_dependency(authentication, users)

    def service() -> SessionInsightsService:
        if insights is None:
            raise HTTPException(503, "La línea de tiempo y las métricas no están disponibles")
        return insights

    def guarded(operation):
        try:
            return operation()
        except InsightsNotFound as error:
            raise HTTPException(404, "No encontrado") from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error

    @router.get("/sessions/{session_id}/timeline")
    def timeline(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: service().timeline(user, session_id))

    @router.get("/sessions/{session_id}/metrics")
    def metrics(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: service().metrics(user, session_id))

    return router
