"""Banco de estímulos y protocolos.

Los estímulos los crean los docentes (para su grupo) y el administrador (para
la institución); los usuarios los usan en sus protocolos, junto con sus
imágenes propias ya aprobadas por su docente (ver user_image_router). La imagen de un
estímulo es la única imagen que sirve la API y nunca es la de una persona evaluada.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from emotv.application import AuthenticationService
from emotv.application.protocol_service import ProtocolDraft, ProtocolNotFound, ProtocolService
from emotv.application.ports import UserRepository
from emotv.application.stimulus_service import StimulusDraft, StimulusNotFound, StimulusService
from emotv.domain import Protocol, ProtocolStep, Stimulus, User
from emotv.domain.protocol import MAX_EXPOSURE_SECONDS, MAX_STEPS
from emotv.infrastructure.vision.stimulus_image import MAX_BYTES
from emotv.interfaces.web.auth_router import create_current_user_dependency


class StimulusResponse(BaseModel):
    id: str
    title: str
    kind: str
    category: str
    expected_expression: str | None
    intensity: str
    min_age: int
    origin: str
    license: str
    scope: str
    # «Para niños» (leve) sirve con niños y adultos; «Para adultos», solo con adultos.
    audience: Literal["children", "adults"]
    created_at: datetime
    approved: bool
    active: bool
    can_manage: bool


class StimulusActive(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool


class StepModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # «stimulus»: se muestra una imagen. «practice»: se pide una expresión y se
    # sostiene; la imagen es una ilustración opcional.
    kind: Literal["stimulus", "practice"] = "stimulus"
    stimulus_id: str | None = Field(default=None, min_length=1, max_length=36)
    exposure_seconds: int = Field(ge=1, le=MAX_EXPOSURE_SECONDS)
    capture_after_seconds: int = Field(default=0, ge=0, le=MAX_EXPOSURE_SECONDS)
    record_verbal_response: bool = False
    # Solo imágenes abstractas: se muestran antes de la calibración, sin capturas.
    shown_before_analyzer: bool = False
    target_expression: str | None = Field(default=None, max_length=32)
    # Los límites los valida el dominio, con sus mensajes en español.
    hold_seconds: int | None = None


class ProtocolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    # Primera pregunta obligatoria: ¿para adultos o para niños?
    for_children: bool
    pre_questionnaire_id: str | None = Field(default=None, max_length=36)
    post_questionnaire_id: str | None = Field(default=None, max_length=36)
    steps: list[StepModel] = Field(min_length=1, max_length=MAX_STEPS)


class ProtocolResponse(BaseModel):
    id: str
    family_id: str
    version: int
    name: str
    description: str
    for_children: bool
    pre_questionnaire_id: str | None
    post_questionnaire_id: str | None
    steps: list[StepModel]
    created_at: datetime
    owned_by_me: bool
    used: bool
    # Una imagen fue eliminada o reclasificada por el docente: hay que reemplazarla.
    needs_image: bool


def create_stimulus_router(
    stimuli: StimulusService | None,
    protocols: ProtocolService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["stimuli"])
    current_user = create_current_user_dependency(authentication, users)

    def stimulus_service() -> StimulusService:
        if stimuli is None:
            raise HTTPException(503, "El banco de estímulos no está configurado")
        return stimuli

    def protocol_service() -> ProtocolService:
        if protocols is None:
            raise HTTPException(503, "Los protocolos no están configurados")
        return protocols

    def guarded(operation):
        try:
            return operation()
        except (StimulusNotFound, ProtocolNotFound) as error:
            raise HTTPException(404, "No encontrado") from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except ValueError as error:  # incluye InvalidStimulusImage
            raise HTTPException(422, str(error)) from error

    def stimulus_response(item: Stimulus, user: User) -> StimulusResponse:
        return StimulusResponse(
            id=item.id, title=item.title, kind=item.kind.value, category=item.category,
            expected_expression=item.expected_expression, intensity=item.intensity.value, min_age=item.min_age,
            origin=item.origin, license=item.license, scope=item.scope.value, audience=item.audience.value,
            created_at=item.created_at,
            approved=item.approved, active=item.active, can_manage=stimulus_service().can_manage(user, item))

    def protocol_response(item: Protocol, user: User) -> ProtocolResponse:
        service = protocol_service()
        return ProtocolResponse(
            id=item.id, family_id=item.family_id, version=item.version, name=item.name,
            description=item.description, for_children=item.for_children,
            pre_questionnaire_id=item.pre_questionnaire_id,
            post_questionnaire_id=item.post_questionnaire_id,
            steps=[StepModel(kind=step.kind.value, stimulus_id=step.stimulus_id,
                             exposure_seconds=step.exposure_seconds,
                             capture_after_seconds=step.capture_after_seconds,
                             record_verbal_response=step.record_verbal_response,
                             shown_before_analyzer=step.shown_before_analyzer,
                             target_expression=step.target_expression, hold_seconds=step.hold_seconds)
                   for step in item.steps],
            created_at=item.created_at, owned_by_me=item.owner_user_id == user.id, used=service.is_used(item),
            needs_image=service.needs_image(item))

    def draft(request: ProtocolRequest) -> ProtocolDraft:
        try:
            steps = tuple(ProtocolStep(step.stimulus_id, step.exposure_seconds, step.capture_after_seconds,
                                       step.record_verbal_response, step.shown_before_analyzer, kind=step.kind,
                                       target_expression=step.target_expression, hold_seconds=step.hold_seconds)
                          for step in request.steps)
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error)) from error
        return ProtocolDraft(name=request.name, description=request.description, for_children=request.for_children,
                             steps=steps, pre_questionnaire_id=request.pre_questionnaire_id,
                             post_questionnaire_id=request.post_questionnaire_id)

    # --- Estímulos -------------------------------------------------------------

    @router.get("/stimuli", response_model=list[StimulusResponse])
    def list_stimuli(for_children: bool = False, user: User = Depends(current_user)):
        """Con for_children, solo los que admite un protocolo para niños."""
        return [stimulus_response(item, user)
                for item in guarded(lambda: stimulus_service().list_for(user, for_children))]

    @router.post("/stimuli", response_model=StimulusResponse, status_code=201)
    async def create_stimulus(
        file: UploadFile = File(...),
        title: str = Form(..., min_length=1, max_length=120),
        kind: Literal["emotional", "abstract"] = Form(...),
        category: str = Form(..., min_length=1, max_length=80),
        intensity: Literal["mild", "moderate"] = Form(...),
        min_age: int = Form(..., ge=1, le=99),
        origin: str = Form(..., min_length=1, max_length=500),
        license: str = Form(..., min_length=1, max_length=300),
        expected_expression: str | None = Form(None, max_length=32),
        not_a_participant_photo: bool = Form(False),
        not_a_projective_test: bool = Form(False),
        user: User = Depends(current_user),
    ):
        data = await file.read(MAX_BYTES + 1)
        draft_item = StimulusDraft(
            title=title, kind=kind, category=category, intensity=intensity, min_age=min_age, origin=origin,
            license=license, expected_expression=expected_expression or None,
            not_a_participant_photo=not_a_participant_photo, not_a_projective_test=not_a_projective_test)
        return stimulus_response(guarded(lambda: stimulus_service().create(user, draft_item, data)), user)

    @router.get("/stimuli/{stimulus_id}", response_model=StimulusResponse)
    def get_stimulus(stimulus_id: str, user: User = Depends(current_user)):
        return stimulus_response(guarded(lambda: stimulus_service().get(user, stimulus_id)), user)

    @router.get("/stimuli/{stimulus_id}/file", response_class=Response)
    def stimulus_file(stimulus_id: str, user: User = Depends(current_user)):
        """La imagen del estímulo (nunca la de una persona evaluada)."""
        content_type, data = guarded(lambda: stimulus_service().image(user, stimulus_id))
        return Response(content=data, media_type=content_type)

    @router.post("/stimuli/{stimulus_id}/approve", response_model=StimulusResponse)
    def approve_stimulus(stimulus_id: str, user: User = Depends(current_user)):
        return stimulus_response(guarded(lambda: stimulus_service().approve(user, stimulus_id)), user)

    @router.put("/stimuli/{stimulus_id}/active", response_model=StimulusResponse)
    def set_stimulus_active(stimulus_id: str, request: StimulusActive, user: User = Depends(current_user)):
        return stimulus_response(guarded(lambda: stimulus_service().set_active(user, stimulus_id, request.active)),
                                 user)

    # --- Protocolos ------------------------------------------------------------

    @router.get("/protocols", response_model=list[ProtocolResponse])
    def list_protocols(user: User = Depends(current_user)):
        return [protocol_response(item, user) for item in guarded(lambda: protocol_service().list_for(user))]

    @router.post("/protocols", response_model=ProtocolResponse, status_code=201)
    def create_protocol(request: ProtocolRequest, user: User = Depends(current_user)):
        return protocol_response(guarded(lambda: protocol_service().create(user, draft(request))), user)

    @router.get("/protocols/{protocol_id}", response_model=ProtocolResponse)
    def get_protocol(protocol_id: str, user: User = Depends(current_user)):
        return protocol_response(guarded(lambda: protocol_service().get(user, protocol_id)), user)

    @router.put("/protocols/{protocol_id}", response_model=ProtocolResponse)
    def edit_protocol(protocol_id: str, request: ProtocolRequest, user: User = Depends(current_user)):
        """Si la versión ya se usó en una sesión, responde con la versión nueva."""
        return protocol_response(guarded(lambda: protocol_service().edit(user, protocol_id, draft(request))), user)

    return router
