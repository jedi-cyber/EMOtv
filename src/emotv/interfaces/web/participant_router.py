"""Participantes: registro, consulta, vencimientos y eliminación con acta.

Todo acceso pasa por can_access_participant (en ParticipantService). Ninguna
respuesta incluye imágenes: las capturas se descartan en el servidor.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from emotv.application import AuthenticationService
from emotv.application.commitment_service import CommitmentRequired
from emotv.application.participant_service import ChildNoticeRequired, ParticipantNotFound, ParticipantService
from emotv.application.ports import UserRepository
from emotv.application.ports.privacy_repositories import DeletionCertificate, ErasureVerificationError
from emotv.domain import Participant, User
from emotv.interfaces.web.auth_router import create_current_user_dependency

MODULE_UNAVAILABLE = ("El módulo de participantes no está disponible: el servidor no tiene configurada "
                      "la clave de cifrado de datos sensibles.")


class ParticipantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["adult", "child"]
    notes: str | None = Field(default=None, max_length=2000)
    # Versión del aviso sobre datos de menores, la primera vez que se registra a un niño.
    child_notice_version: str | None = Field(default=None, max_length=32)


class ParticipantResponse(BaseModel):
    id: str
    code: str
    kind: str
    created_at: datetime
    expires_at: datetime
    notes: str | None
    registered_by_me: bool
    deletion_requested_at: datetime | None


class DeletionCertificateResponse(BaseModel):
    id: str
    participant_code: str
    deleted_at: datetime
    counts: dict[str, int]
    verified: bool


def create_participant_router(
    participants: ParticipantService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["participants"])
    current_user = create_current_user_dependency(authentication, users)

    def service() -> ParticipantService:
        if participants is None:
            raise HTTPException(503, MODULE_UNAVAILABLE)
        return participants

    def response(item: Participant, user: User) -> ParticipantResponse:
        return ParticipantResponse(
            id=item.id, code=item.code, kind=item.kind.value, created_at=item.created_at,
            expires_at=service().expires_at(item), notes=item.notes,
            registered_by_me=item.registered_by_user_id == user.id,
            deletion_requested_at=item.deletion_requested_at)

    def certificate_response(item: DeletionCertificate) -> DeletionCertificateResponse:
        return DeletionCertificateResponse(id=item.id, participant_code=item.participant_code,
                                           deleted_at=item.deleted_at, counts=item.counts, verified=item.verified)

    def guarded(operation):
        try:
            return operation()
        except ParticipantNotFound as error:
            raise HTTPException(404, "Participante no encontrado") from error
        except ChildNoticeRequired as error:
            raise HTTPException(428, str(error)) from error
        except CommitmentRequired as error:
            raise HTTPException(428, str(error)) from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except ErasureVerificationError as error:
            raise HTTPException(500, "La verificación de la eliminación falló; no se borró nada") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @router.get("/participants", response_model=list[ParticipantResponse])
    def list_participants(user: User = Depends(current_user)):
        return [response(item, user) for item in guarded(lambda: service().list_for(user))]

    @router.post("/participants", response_model=ParticipantResponse, status_code=201)
    def register(request: ParticipantCreate, user: User = Depends(current_user)):
        item = guarded(lambda: service().register(user, request.kind, request.notes, request.child_notice_version))
        return response(item, user)

    @router.get("/participants/expiring", response_model=list[ParticipantResponse])
    def expiring(user: User = Depends(current_user)):
        return [response(item, user) for item in guarded(lambda: service().expiring(user))]

    @router.get("/participants/{participant_id}", response_model=ParticipantResponse)
    def get_participant(participant_id: str, user: User = Depends(current_user)):
        return response(guarded(lambda: service().get(user, participant_id)), user)

    @router.post("/participants/{participant_id}/deletion-request", response_model=ParticipantResponse)
    def request_deletion(participant_id: str, user: User = Depends(current_user)):
        return response(guarded(lambda: service().request_deletion(user, participant_id)), user)

    @router.post("/participants/{participant_id}/delete", response_model=DeletionCertificateResponse)
    def delete_participant(participant_id: str, user: User = Depends(current_user)):
        return certificate_response(guarded(lambda: service().delete(user, participant_id)))

    @router.get("/participant-deletions", response_model=list[DeletionCertificateResponse])
    def list_certificates(user: User = Depends(current_user)):
        return [certificate_response(item) for item in guarded(lambda: service().certificates_for(user))]

    @router.get("/participant-deletions/{certificate_id}", response_model=DeletionCertificateResponse)
    def get_certificate(certificate_id: str, user: User = Depends(current_user)):
        return certificate_response(guarded(lambda: service().certificate(user, certificate_id)))

    @router.post("/participant-deletions/{certificate_id}/print", response_model=DeletionCertificateResponse)
    def print_certificate(certificate_id: str, user: User = Depends(current_user)):
        """Registra la impresión del acta en la auditoría y devuelve su contenido."""
        return certificate_response(guarded(lambda: service().certificate(user, certificate_id, printing=True)))

    return router
