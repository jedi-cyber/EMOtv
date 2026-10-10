from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from emotv.application import AuthenticationService
from emotv.application.expression_catalog_service import ExpressionCatalogService
from emotv.application.ports import UserRepository
from emotv.domain import Role, User
from emotv.domain.expression_info import (
    COMMON_LIMITATION, LABEL_MAX_LENGTH, TEXT_MAX_LENGTH, TEXT_MIN_LENGTH, ExpressionInfo,
)
from emotv.interfaces.web.auth_router import create_current_user_dependency

def _text():
    return Field(min_length=TEXT_MIN_LENGTH, max_length=TEXT_MAX_LENGTH)


class ExpressionInfoResponse(BaseModel):
    expression_key: str
    label_es: str
    what_it_is: str
    why_it_occurs: str
    facial_cues: str
    practice_tip: str
    limitation_note: str
    common_limitation: str
    review_status: Literal["draft", "reviewed"]
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    updated_at: datetime

    @classmethod
    def from_domain(cls, info: ExpressionInfo) -> "ExpressionInfoResponse":
        return cls(
            expression_key=info.expression_key, label_es=info.label_es,
            what_it_is=info.what_it_is, why_it_occurs=info.why_it_occurs,
            facial_cues=info.facial_cues, practice_tip=info.practice_tip,
            limitation_note=info.limitation_note, common_limitation=COMMON_LIMITATION,
            review_status=info.review_status.value, reviewed_by_user_id=info.reviewed_by_user_id,
            reviewed_at=info.reviewed_at, updated_at=info.updated_at,
        )


class ExpressionInfoUpdateRequest(BaseModel):
    label_es: str = Field(min_length=1, max_length=LABEL_MAX_LENGTH)
    what_it_is: str = _text()
    why_it_occurs: str = _text()
    facial_cues: str = _text()
    practice_tip: str = _text()
    limitation_note: str = _text()
    review_status: Literal["draft", "reviewed"] = "draft"


def expression_payload(info: ExpressionInfo | None) -> dict[str, object] | None:
    """Mismo contenido que GET /expressions/{key}, serializable para el WebSocket."""
    return None if info is None else ExpressionInfoResponse.from_domain(info).model_dump(mode="json")


def create_expression_router(
    catalog: ExpressionCatalogService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    on_change: Callable[[], None] | None = None,
) -> APIRouter:
    """``on_change`` se llama tras editar un texto (p. ej. para invalidar el conocimiento de Emi)."""
    router = APIRouter(prefix="/expressions", tags=["expressions"])
    current_user = create_current_user_dependency(authentication, users)

    def require_catalog() -> ExpressionCatalogService:
        if catalog is None:
            raise HTTPException(503, "Catálogo de expresiones no configurado")
        return catalog

    @router.get("", response_model=list[ExpressionInfoResponse])
    def list_expressions(_: User = Depends(current_user)) -> list[ExpressionInfoResponse]:
        return [ExpressionInfoResponse.from_domain(item) for item in require_catalog().list_all()]

    @router.get("/{expression_key}", response_model=ExpressionInfoResponse)
    def get_expression(expression_key: str, _: User = Depends(current_user)) -> ExpressionInfoResponse:
        info = require_catalog().get(expression_key)
        if info is None:
            raise HTTPException(404, "Expresión no encontrada")
        return ExpressionInfoResponse.from_domain(info)

    @router.put("/{expression_key}", response_model=ExpressionInfoResponse)
    def update_expression(
        expression_key: str, request: ExpressionInfoUpdateRequest, user: User = Depends(current_user),
    ) -> ExpressionInfoResponse:
        if user.role is not Role.ADMIN:
            raise HTTPException(403, "Solo administración puede editar el catálogo de expresiones")
        data = request.model_dump()
        try:
            updated = require_catalog().update(
                expression_key, editor_user_id=user.id, review_status=data.pop("review_status"), **data,
            )
        except KeyError as error:
            raise HTTPException(404, "Expresión no encontrada") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if on_change is not None:
            on_change()
        return ExpressionInfoResponse.from_domain(updated)

    return router
