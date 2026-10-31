"""Validación de los modelos con adultos voluntarios (docs/expression-practice.md).

El protocolo de ejemplo solo lo agregan cuentas de voluntarios en modo demo. La
exportación es agregada y solo para administración (superadmin); el CSV se arma
en memoria y no se guarda en el servidor.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from emotv.application import AuthenticationService
from emotv.application.practice_validation_service import PracticeValidationService
from emotv.application.ports import UserRepository
from emotv.domain import User
from emotv.interfaces.web.auth_router import create_current_user_dependency

CSV_FILENAME = "validacion-practica-agregada.csv"


def create_practice_validation_router(
    validation: PracticeValidationService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["practice-validation"])
    current_user = create_current_user_dependency(authentication, users)

    def service() -> PracticeValidationService:
        if validation is None:
            raise HTTPException(503, "La validación de los modelos no está disponible")
        return validation

    @router.get("/practice-validation/protocol")
    def status(user: User = Depends(current_user)) -> dict[str, Any]:
        """Si la cuenta puede agregar el protocolo «Validación con adultos» y si ya lo tiene."""
        if validation is None:
            return {"available": False, "protocol_id": None}
        available = validation.available(user)
        found = validation.current_protocol(user) if available else None
        return {"available": available, "protocol_id": found.id if found else None}

    @router.post("/practice-validation/protocol", status_code=201)
    def add(user: User = Depends(current_user)) -> dict[str, Any]:
        try:
            protocol = service().ensure_protocol(user)
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        return {"protocol_id": protocol.id, "name": protocol.name}

    @router.get("/practice-validation/export.csv", response_class=Response)
    def export(user: User = Depends(current_user)) -> Response:
        try:
            text = service().export_csv(user)
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        return Response(content=text, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{CSV_FILENAME}"',
                                 "Cache-Control": "no-store"})

    return router
