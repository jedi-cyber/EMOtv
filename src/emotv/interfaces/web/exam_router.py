"""Examen simulado: rutas del docente. Crear, «Recibí los consentimientos de
todos», Iniciar y Terminar. Nada más que configurar.

Las restricciones se aplican en ExamService: solo un docente activo, dueño del
examen. Las estaciones (sesiones) se muestran por código y estado, nunca con
imágenes ni expresiones en vivo.

Una estación se une con el código del examen, sin cuenta (POST /exam-stations),
y luego usa las rutas de la pantalla de la persona (/participant-view/...).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from emotv.application import AuthenticationService
from emotv.application.commitment_service import CommitmentRequired
from emotv.application.exam_service import ExamConflict, ExamNotFound, ExamService
from emotv.application.ports import UserRepository
from emotv.domain import User
from emotv.interfaces.web.auth_router import create_current_user_dependency


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    join_code: str = Field(min_length=1, max_length=16)


def create_exam_router(
    exams: ExamService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["exams"])
    current_user = create_current_user_dependency(authentication, users)

    def service() -> ExamService:
        if exams is None:
            raise HTTPException(503, "Los exámenes no están disponibles: falta la base de datos")
        return exams

    def guarded(operation):
        try:
            return operation()
        except ExamNotFound as error:
            raise HTTPException(404, "Examen no encontrado") from error
        except CommitmentRequired as error:
            raise HTTPException(428, str(error)) from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except ExamConflict as error:
            raise HTTPException(409, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error

    @router.post("/exams", status_code=201)
    def create(user: User = Depends(current_user)) -> dict[str, Any]:
        """Un clic: EMOtv genera el código que escriben las estaciones."""
        exam = guarded(lambda: service().create(user))
        return guarded(lambda: service().detail(user, exam.id))

    @router.get("/exams")
    def list_exams(user: User = Depends(current_user)) -> list[dict[str, Any]]:
        return list(guarded(lambda: service().list_for(user)))

    @router.get("/exams/{exam_id}")
    def detail(exam_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: service().detail(user, exam_id))

    @router.post("/exams/{exam_id}/consents")
    def confirm_consents(exam_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """«Recibí los consentimientos de todos»: las estaciones unidas hasta ahora."""
        confirmed = guarded(lambda: service().confirm_consents(user, exam_id))
        return {"confirmed": confirmed, **guarded(lambda: service().detail(user, exam_id))}

    @router.post("/exams/{exam_id}/start")
    def start(exam_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        guarded(lambda: service().start(user, exam_id))
        return guarded(lambda: service().detail(user, exam_id))

    @router.post("/exams/{exam_id}/finish")
    def finish(exam_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        guarded(lambda: service().finish(user, exam_id))
        return guarded(lambda: service().detail(user, exam_id))

    @router.post("/exam-stations", status_code=201)
    def join(request: JoinRequest) -> dict[str, str]:
        """La estación escribe el código del examen. Recibe el enlace de su pantalla
        y el código de su sesión, para anotarlo en el consentimiento firmado."""
        try:
            return guarded(lambda: service().join(request.join_code))
        except HTTPException as error:
            if error.status_code == 404:
                raise HTTPException(404, "El código no corresponde a un examen abierto") from error
            raise

    return router
