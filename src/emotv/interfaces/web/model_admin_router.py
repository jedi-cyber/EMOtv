"""Página "Modelos": estado de los modelos locales y elección del predeterminado.

Solo el superadministrador (soporte técnico) consulta y cambia esta
configuración. Los textos describen disponibilidad, nunca precisión.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from emotv.application import AuthenticationService
from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.application.local_model_service import LocalModelService, ModelNotAdmitted
from emotv.application.ports import UserRepository
from emotv.domain import Role, User
from emotv.interfaces.web.auth_router import create_current_user_dependency

LocalModelId = Literal["hsemotion_enet_b0_8_best_afew", "ferplus_onnx"]


class ModelChecks(BaseModel):
    weights_verified: bool
    benchmark_current: bool


class LocalModelStatus(BaseModel):
    model_id: str
    name: str
    version: str
    state: str
    reasons: list[str]
    checks: ModelChecks
    p95_ms: float | None
    # p95 del cuadro completo por sesiones simultáneas ({"1": ms, "2": ms, "4": ms})
    # según el benchmark; solo informativo, nulo si la medición no lo trae.
    concurrent_frame_p95_ms: dict[str, float] | None
    is_default: bool


class LocalModelSettingsResponse(BaseModel):
    default_model_id: str
    changed_by: str | None
    changed_at: datetime | None
    fallback_model_id: str | None
    fallback_at: datetime | None
    models: list[LocalModelStatus]


class DefaultModelRequest(BaseModel):
    model_id: LocalModelId


def create_model_admin_router(
    local_models: LocalModelService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(prefix="/admin/models", tags=["models"])
    current_user = create_current_user_dependency(authentication, users)
    catalog = EmotionModelCatalog()

    def require_superadmin(user: User) -> LocalModelService:
        if user.role is not Role.SUPERADMIN:
            raise HTTPException(403, "Solo el superadministrador puede gestionar los modelos")
        if local_models is None:
            raise HTTPException(503, "Gestión de modelos no configurada")
        return local_models

    def response(service: LocalModelService) -> LocalModelSettingsResponse:
        settings = service.settings()
        changed_by = users.get_by_id(settings.changed_by_user_id) if users and settings.changed_by_user_id else None
        statuses = []
        for model_id, admission, is_default in service.status():
            admission = admission or dict(state="BLOCKED", reasons=["Evaluación de modelos no configurada"])
            checks = admission.get("checks") or {}
            metrics = admission.get("metrics") or {}
            model = catalog.get(model_id)
            statuses.append(LocalModelStatus(
                model_id=model_id, name=model.name, version=model.version,
                state=admission.get("state", "BLOCKED"), reasons=list(admission.get("reasons", [])),
                checks=ModelChecks(weights_verified=bool(checks.get("weights_verified")),
                                   benchmark_current=bool(checks.get("benchmark_current"))),
                p95_ms=metrics.get("p95_ms"), concurrent_frame_p95_ms=metrics.get("concurrent_frame_p95_ms"),
                is_default=is_default,
            ))
        return LocalModelSettingsResponse(
            default_model_id=settings.default_model_id,
            changed_by=changed_by.email if changed_by else None,
            changed_at=settings.changed_at,
            fallback_model_id=settings.fallback_model_id,
            fallback_at=settings.fallback_at,
            models=statuses,
        )

    @router.get("", response_model=LocalModelSettingsResponse)
    def get_models(user: User = Depends(current_user)) -> LocalModelSettingsResponse:
        return response(require_superadmin(user))

    @router.put("/default", response_model=LocalModelSettingsResponse)
    def set_default(request: DefaultModelRequest, user: User = Depends(current_user)) -> LocalModelSettingsResponse:
        service = require_superadmin(user)
        try:
            service.set_default(request.model_id, user.id)
        except ModelNotAdmitted as error:
            raise HTTPException(409, str(error)) from error
        except KeyError as error:
            raise HTTPException(422, "Modelo local no reconocido") from error
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error
        return response(service)

    return router
