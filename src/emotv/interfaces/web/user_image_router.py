"""Imágenes propias de los usuarios (/own-stimuli), su revisión por el docente
y los avisos (/notices). En la API son estímulos: ninguna ruta de consulta se
llama como una imagen.

Las imágenes que sirve este router son estímulos subidos por usuarios, nunca
fotos de personas evaluadas: la detección automática rechaza las que parecen
mostrar a una persona y el docente revisa todas antes de que se usen.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from emotv.application import AuthenticationService
from emotv.application.ports import UserRepository
from emotv.application.stimulus_service import StimulusNotFound
from emotv.application.user_image_service import MAX_BATCH, ImageUpload, UserImageService
from emotv.domain import Stimulus, User
from emotv.infrastructure.vision.person_detection import PersonCheckUnavailable
from emotv.infrastructure.vision.stimulus_image import MAX_BYTES
from emotv.interfaces.web.auth_router import create_current_user_dependency


class ImageResponse(BaseModel):
    id: str
    title: str
    origin: str
    audience: Literal["children", "adults"]
    status: Literal["pending", "approved"]
    possible_person: bool
    batch_id: str | None
    created_at: datetime
    # Solo las pendientes: fecha en que se eliminan si nadie las revisa.
    expires_at: datetime | None
    # Solo en la revisión del docente: correo de quien la subió.
    uploaded_by: str | None = None


class UploadItemResponse(BaseModel):
    title: str
    accepted: bool
    message: str | None
    image: ImageResponse | None


class UploadResponse(BaseModel):
    batch_id: str
    results: list[UploadItemResponse]


class ReviewBatch(BaseModel):
    batch_id: str
    uploaded_by: str
    uploaded_at: datetime
    images: list[ImageResponse]


class ReviewResponse(BaseModel):
    pending: list[ReviewBatch]
    approved: list[ImageResponse]


class ReviewCount(BaseModel):
    pending: int


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_ids: list[str] = Field(min_length=1, max_length=200)
    decision: Literal["children", "adults", "delete"]
    reason: str | None = Field(default=None, max_length=300)


class NoticeResponse(BaseModel):
    id: str
    message: str
    created_at: datetime


def create_user_image_router(
    images: UserImageService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["images"])
    current_user = create_current_user_dependency(authentication, users)

    def service() -> UserImageService:
        if images is None:
            raise HTTPException(503, "Las imágenes propias no están configuradas")
        return images

    def guarded(operation: Callable):
        try:
            return operation()
        except StimulusNotFound as error:
            raise HTTPException(404, "No encontrado") from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except PersonCheckUnavailable as error:
            raise HTTPException(503, "La revisión automática de imágenes no está disponible; inténtalo más tarde"
                                ) from error
        except ValueError as error:  # incluye InvalidStimulusImage
            raise HTTPException(422, str(error)) from error

    def email_of(user_id: str) -> str:
        found = users.get_by_id(user_id) if users is not None else None
        return found.email if found is not None else "Cuenta eliminada"

    def response(item: Stimulus, uploaded_by: str | None = None) -> ImageResponse:
        return ImageResponse(
            id=item.id, title=item.title, origin=item.origin, audience=item.audience.value,
            status="pending" if item.pending else "approved", possible_person=item.possible_person,
            batch_id=item.upload_batch_id, created_at=item.created_at,
            expires_at=(item.created_at + timedelta(days=service().settings.review_days)) if item.pending else None,
            uploaded_by=uploaded_by)

    # --- Usuario ---------------------------------------------------------------

    @router.post("/own-stimuli", response_model=UploadResponse, status_code=201)
    async def upload_images(
        files: list[UploadFile] = File(...),
        titles: list[str] = Form(...),
        origins: list[str] = Form(...),
        audiences: list[Literal["children", "adults"]] = Form(...),
        rights_confirmed: list[bool] = Form(...),
        user: User = Depends(current_user),
    ):
        """Un lote: cada imagen con su nombre, de dónde es, para quién es y la
        casilla «No es una foto de una persona que pueda identificarse, y tengo
        derecho a usarla»."""
        if len(files) > MAX_BATCH:
            raise HTTPException(422, f"Sube como máximo {MAX_BATCH} imágenes a la vez")
        if not len(files) == len(titles) == len(origins) == len(audiences) == len(rights_confirmed):
            raise HTTPException(422, "Cada imagen necesita su nombre, origen, público y confirmación")
        if any(len(text) > limit for values, limit in ((titles, 120), (origins, 500)) for text in values):
            raise HTTPException(422, "El nombre admite 120 caracteres y el origen, 500")
        items = [ImageUpload(data=await file.read(MAX_BYTES + 1), title=title, origin=origin, audience=audience,
                             rights_confirmed=rights)
                 for file, title, origin, audience, rights in zip(files, titles, origins, audiences,
                                                                  rights_confirmed)]
        batch_id, results = guarded(lambda: service().upload(user, items))
        return UploadResponse(batch_id=batch_id, results=[
            UploadItemResponse(title=item.title, accepted=item.accepted, message=item.message,
                               image=response(item.image) if item.image is not None else None)
            for item in results])

    @router.get("/own-stimuli", response_model=list[ImageResponse])
    def own_images(user: User = Depends(current_user)):
        return [response(item) for item in guarded(lambda: service().list_own(user))]

    @router.get("/own-stimuli/{stimulus_id}/file", response_class=Response)
    def image_file(stimulus_id: str, preview: bool = False, user: User = Depends(current_user)):
        """Para quien la subió y su docente. preview=true: vista ampliada del docente (se audita)."""
        content_type, data = guarded(lambda: service().image(user, stimulus_id, preview))
        return Response(content=data, media_type=content_type, headers={"Cache-Control": "no-store"})

    # --- Docente ---------------------------------------------------------------

    @router.get("/own-stimuli/review", response_model=ReviewResponse)
    def review(user: User = Depends(current_user)):
        """Pendientes agrupadas por lote (correo de quien subió y fecha) y las ya aprobadas."""
        items = guarded(lambda: service().review_list(user))
        emails = {owner: email_of(owner) for owner in {item.owner_user_id for item in items}}
        batches: dict[str, ReviewBatch] = {}
        for item in items:
            if not item.pending:
                continue
            key = item.upload_batch_id or item.id
            batch = batches.get(key)
            if batch is None:
                batch = batches[key] = ReviewBatch(batch_id=key, uploaded_by=emails[item.owner_user_id],
                                                   uploaded_at=item.created_at, images=[])
            batch.images.append(response(item, emails[item.owner_user_id]))
        return ReviewResponse(
            pending=sorted(batches.values(), key=lambda batch: batch.uploaded_at),
            approved=[response(item, emails[item.owner_user_id]) for item in items if not item.pending])

    @router.get("/own-stimuli/review/count", response_model=ReviewCount)
    def review_count(user: User = Depends(current_user)):
        return ReviewCount(pending=guarded(lambda: service().pending_count(user)))

    @router.post("/own-stimuli/review", response_model=list[ImageResponse])
    def decide(request: ReviewRequest, user: User = Depends(current_user)):
        """Varias imágenes a la vez: «Para niños», «Para adultos» o «Eliminar» (con motivo opcional)."""
        updated = guarded(lambda: service().decide(user, request.image_ids, request.decision, request.reason))
        return [response(item) for item in updated]

    # --- Avisos ----------------------------------------------------------------

    @router.get("/notices", response_model=list[NoticeResponse])
    def notices(user: User = Depends(current_user)):
        return [NoticeResponse(id=item.id, message=item.message, created_at=item.created_at)
                for item in service().notices_for(user)]

    @router.post("/notices/{notice_id}/read", status_code=204)
    def read_notice(notice_id: str, user: User = Depends(current_user)):
        guarded(lambda: service().mark_notice_read(user, notice_id))
        return Response(status_code=204)

    return router
