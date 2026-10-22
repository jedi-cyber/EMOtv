"""Compromiso de confidencialidad y consulta de la auditoría.

La auditoría solo se consulta (administrador y superadministrador): no existe
ninguna operación de la API que la edite o la borre.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from emotv.application import AuthenticationService
from emotv.application.audit_service import AuditService
from emotv.application.commitment_service import CHILD_NOTICE, COMMITMENT, CommitmentService
from emotv.application.ports import UserRepository
from emotv.application.ports.privacy_repositories import AuditFilter
from emotv.domain import User
from emotv.domain.role import CONDUCTOR_ROLES, MANAGEMENT_ROLES
from emotv.interfaces.web.auth_router import create_current_user_dependency


class VersionedTextResponse(BaseModel):
    kind: Literal["commitment", "child_notice"]
    version: str
    provisional: bool
    content: str
    # Siempre falso para el administrador y el superadministrador, que no lo aceptan.
    required: bool
    accepted: bool


class AcceptRequest(BaseModel):
    version: str = Field(min_length=1, max_length=32)


class AuditEntryResponse(BaseModel):
    id: str
    occurred_at: datetime
    actor_user_id: str | None
    actor_role: str | None
    action: str
    resource_type: str
    resource_id: str | None
    result: str


def create_privacy_router(
    commitments: CommitmentService | None,
    audit: AuditService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["privacy"])
    current_user = create_current_user_dependency(authentication, users)

    def require_commitments() -> CommitmentService:
        if commitments is None:
            raise HTTPException(503, "Compromiso de confidencialidad no configurado")
        return commitments

    def text_response(user: User, kind: str) -> VersionedTextResponse:
        service = require_commitments()
        text = service.text(kind)
        conductor = user.role in CONDUCTOR_ROLES
        accepted = conductor and service.has_accepted(user, kind)
        return VersionedTextResponse(kind=kind, version=text.version, provisional=text.provisional,
                                     content=text.content, required=conductor and not accepted, accepted=accepted)

    def accept(kind: str, request: AcceptRequest, user: User) -> VersionedTextResponse:
        try:
            require_commitments().accept(user, request.version, kind)
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return text_response(user, kind)

    @router.get("/commitment", response_model=VersionedTextResponse)
    def get_commitment(user: User = Depends(current_user)) -> VersionedTextResponse:
        return text_response(user, COMMITMENT)

    @router.post("/commitment/accept", response_model=VersionedTextResponse)
    def accept_commitment(request: AcceptRequest, user: User = Depends(current_user)) -> VersionedTextResponse:
        return accept(COMMITMENT, request, user)

    @router.get("/commitment/child-notice", response_model=VersionedTextResponse)
    def get_child_notice(user: User = Depends(current_user)) -> VersionedTextResponse:
        return text_response(user, CHILD_NOTICE)

    @router.post("/commitment/child-notice/accept", response_model=VersionedTextResponse)
    def accept_child_notice(request: AcceptRequest, user: User = Depends(current_user)) -> VersionedTextResponse:
        return accept(CHILD_NOTICE, request, user)

    @router.get("/audit", response_model=list[AuditEntryResponse])
    def list_audit(
        user: User = Depends(current_user),
        actor_user_id: str | None = Query(default=None, max_length=64),
        action: str | None = Query(default=None, max_length=32),
        resource_type: str | None = Query(default=None, max_length=32),
        resource_id: str | None = Query(default=None, max_length=64),
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> list[AuditEntryResponse]:
        if user.role not in MANAGEMENT_ROLES:
            raise HTTPException(403, "La auditoría la consultan el administrador y el superadministrador")
        if audit is None:
            raise HTTPException(503, "Auditoría no configurada")
        entries = audit.query(AuditFilter(actor_user_id=actor_user_id, action=action, resource_type=resource_type,
                                          resource_id=resource_id, since=since, until=until), limit, offset)
        return [AuditEntryResponse(id=item.id, occurred_at=item.occurred_at, actor_user_id=item.actor_user_id,
                                   actor_role=item.actor_role, action=item.action.value,
                                   resource_type=item.resource_type, resource_id=item.resource_id,
                                   result=item.result.value) for item in entries]

    return router

