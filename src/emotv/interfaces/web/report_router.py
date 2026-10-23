"""Reporte de sesión con revisión del docente. La impresión la hace el navegador;
el servidor no genera archivos."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from emotv.application import AuthenticationService
from emotv.application.ports import UserRepository
from emotv.application.report_service import ReportConflict, ReportNotFound, ReportService
from emotv.domain import User
from emotv.domain.report import MAX_COMMENT, MAX_NARRATIVE
from emotv.interfaces.web.auth_router import create_current_user_dependency


class NarrativeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    narrative: str = Field(max_length=MAX_NARRATIVE)


class CommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: Literal["timeline", "metrics", "questionnaires", "narrative", "general"]
    text: str = Field(min_length=1, max_length=MAX_COMMENT)


def create_report_router(
    reports: ReportService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["reports"])
    current_user = create_current_user_dependency(authentication, users)

    def service() -> ReportService:
        if reports is None:
            raise HTTPException(503, "Los reportes no están disponibles: falta la clave de cifrado de datos sensibles")
        return reports

    def guarded(operation):
        try:
            return operation()
        except ReportNotFound as error:
            raise HTTPException(404, "Reporte no encontrado") from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except ReportConflict as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    def view(user: User, report_id: str) -> dict[str, Any]:
        return service().get(user, report_id)

    @router.post("/sessions/{session_id}/report", status_code=201)
    def create(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: view(user, service().create(user, session_id).id))

    @router.get("/sessions/{session_id}/report")
    def for_session(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: service().for_session(user, session_id))

    @router.get("/reports/{report_id}")
    def get(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: view(user, report_id))

    @router.put("/reports/{report_id}")
    def edit(report_id: str, request: NarrativeRequest, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: view(user, service().edit(user, report_id, request.narrative).id))

    @router.post("/reports/{report_id}/submit")
    def submit(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: view(user, service().submit(user, report_id).id))

    @router.post("/reports/{report_id}/comments", status_code=201)
    def comment(report_id: str, request: CommentRequest, user: User = Depends(current_user)) -> dict[str, Any]:
        guarded(lambda: service().comment(user, report_id, request.section, request.text))
        return guarded(lambda: view(user, report_id))

    @router.post("/reports/{report_id}/return")
    def return_report(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: view(user, service().return_with_comments(user, report_id).id))

    @router.post("/reports/{report_id}/approve")
    def approve(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: view(user, service().approve(user, report_id).id))

    @router.post("/reports/{report_id}/new-version", status_code=201)
    def new_version(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: view(user, service().new_version(user, report_id).id))

    @router.post("/reports/{report_id}/print")
    def print_view(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """Registra la impresión en la auditoría y devuelve el contenido imprimible."""
        return guarded(lambda: service().print_view(user, report_id))

    return router
