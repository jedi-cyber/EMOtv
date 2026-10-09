from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from emotv.application import AuthenticationService
from emotv.application.ports import UserRepository
from emotv.application.recommendation_config_service import (
    MAX_ACTIVITIES_PER_EXPRESSION,
    RecommendationConfigService,
)
from emotv.domain import Role, User
from emotv.interfaces.web.auth_router import create_current_user_dependency


class RecommendationResponse(BaseModel):
    expression_key: str
    activity_ids: list[str]


class RecommendationUpdateRequest(BaseModel):
    # El orden de la lista es la prioridad; una lista vacía deja la expresión sin recomendación.
    activity_ids: list[str] = Field(max_length=MAX_ACTIVITIES_PER_EXPRESSION)


def create_recommendation_router(
    config: RecommendationConfigService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(prefix="/recommendations", tags=["recommendations"])
    current_user = create_current_user_dependency(authentication, users)

    def require_admin(user: User) -> RecommendationConfigService:
        if user.role is not Role.ADMIN:
            raise HTTPException(403, "Solo administración puede gestionar las recomendaciones")
        if config is None:
            raise HTTPException(503, "Recomendaciones no configuradas")
        return config

    @router.get("", response_model=list[RecommendationResponse])
    def list_recommendations(user: User = Depends(current_user)) -> list[RecommendationResponse]:
        return [RecommendationResponse(expression_key=key, activity_ids=list(ids))
                for key, ids in require_admin(user).list_all().items()]

    @router.get("/{expression_key}", response_model=RecommendationResponse)
    def get_recommendation(expression_key: str, user: User = Depends(current_user)) -> RecommendationResponse:
        service = require_admin(user)
        try:
            return RecommendationResponse(expression_key=expression_key, activity_ids=list(service.get(expression_key)))
        except KeyError as error:
            raise HTTPException(404, "Expresión no encontrada") from error

    @router.put("/{expression_key}", response_model=RecommendationResponse)
    def update_recommendation(
        expression_key: str, request: RecommendationUpdateRequest, user: User = Depends(current_user),
    ) -> RecommendationResponse:
        service = require_admin(user)
        try:
            saved = service.replace(expression_key, request.activity_ids)
        except KeyError as error:
            raise HTTPException(404, "Expresión no encontrada") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return RecommendationResponse(expression_key=expression_key.strip().lower(), activity_ids=list(saved))

    return router
