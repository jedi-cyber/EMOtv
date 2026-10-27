"""Examen simulado: rutas del docente. Crear, «Recibí los consentimientos de
todos», Iniciar y Terminar. Nada más que configurar.

Las restricciones se aplican en ExamService: solo un docente activo, dueño del
examen. Las estaciones (sesiones) se muestran por código y estado, nunca con
imágenes ni expresiones en vivo.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from emotv.application import AuthenticationService
from emotv.application.commitment_service import CommitmentRequired
from emotv.application.exam_service import ExamConflict, ExamNotFound, ExamService
from emotv.application.ports import UserRepository
from emotv.domain import User
from emotv.interfaces.web.auth_router import create_current_user_dependency


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
        except (ExamConflict, RuntimeError) as error:
            raise HTTPException(409, str(error)) from error

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

    return router
