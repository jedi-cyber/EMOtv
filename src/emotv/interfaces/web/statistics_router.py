"""Estadísticas agregadas de sesiones: cuentan sesiones, no personas.

Se calculan en el servidor con las sesiones a las que la cuenta ya tiene
acceso. No se generan archivos: la interfaz copia la tabla al portapapeles.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from emotv.application import AuthenticationService
from emotv.application.ports import UserRepository
from emotv.application.session_statistics_service import SessionStatisticsService, StatisticsFilter
from emotv.domain import User
from emotv.interfaces.web.auth_router import create_current_user_dependency


def create_statistics_router(
    statistics: SessionStatisticsService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["statistics"])
    current_user = create_current_user_dependency(authentication, users)

    @router.get("/statistics")
    def session_statistics(
        scope: Literal["mine", "group"] = "mine",
        date_from: date | None = None,
        date_to: date | None = None,
        protocol: str | None = Query(None, max_length=36, description="Familia del protocolo o «none»"),
        audience: Literal["propia", "adulto", "infantil"] | None = None,
        questionnaire_id: str | None = Query(None, max_length=36),
        user: User = Depends(current_user),
    ) -> dict[str, Any]:
        if statistics is None:
            raise HTTPException(503, "Las estadísticas no están disponibles")
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "La fecha inicial es posterior a la final")
        filters = StatisticsFilter(scope=scope, date_from=date_from, date_to=date_to, protocol=protocol or None,
                                   audience=audience, questionnaire_id=questionnaire_id or None)
        try:
            return statistics.statistics(user, filters)
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    return router
