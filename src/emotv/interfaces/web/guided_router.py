"""Sesión guiada: rutas de quien conduce la sesión y de la vista del participante.

La vista del participante usa un enlace propio (sin cuenta) y solo recibe lo
que debe mostrar: nunca expresiones, probabilidades, calidad ni notas. Los
cuadros de su cámara se analizan en memoria y se descartan.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from emotv.application import AuthenticationService
from emotv.application.guided_session_service import GuidedConflict, GuidedNotFound, GuidedSessionService
from emotv.application.ports import UserRepository
from emotv.domain import User
from emotv.domain.guided_session import ABSTRACT_NOTICE, MAX_NOTE_LENGTH
from emotv.interfaces.web.auth_router import create_current_user_dependency

MAX_FRAME_BYTES = 1_000_000


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commitment_reminder: bool = False
    authorization_confirmed: bool = False
    guardian_present: bool = False
    child_assent: bool = False


class StopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["participant", "guardian", "conductor"]


class MarkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["distracted", "laughed", "asked_to_stop", "cried", "note"]
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


class VerbalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)


class ParticipantView(BaseModel):
    """Lo único que recibe la vista del participante."""

    phase: str
    message: str | None
    stimulus: dict[str, str] | None
    remaining_seconds: float | None
    capture_frames: bool
    frame_interval_ms: int
    abstract_notice: str | None


def create_guided_router(
    guided: GuidedSessionService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    stimulus_image=None,       # Callable[[str], tuple[str, bytes] | None]
    decode_frame=None,         # Callable[[bytes], ndarray | None]
) -> APIRouter:
    router = APIRouter(tags=["guided-sessions"])
    current_user = create_current_user_dependency(authentication, users)

    def service() -> GuidedSessionService:
        if guided is None:
            raise HTTPException(503, "Las sesiones guiadas no están disponibles: falta la clave de cifrado de datos "
                                     "sensibles o la base de datos")
        return guided

    def guarded(operation):
        try:
            return operation()
        except GuidedNotFound as error:
            raise HTTPException(404, "Sesión guiada no encontrada") from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except GuidedConflict as error:
            raise HTTPException(409, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    def conductor(state: dict[str, Any]) -> dict[str, Any]:
        state["abstract_notice"] = ABSTRACT_NOTICE if state.get("has_abstract") else None
        return state

    # --- Quien conduce la sesión ---------------------------------------------------

    @router.post("/guided-sessions/{session_id}", status_code=201)
    def create(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        run, token = guarded(lambda: service().create(user, session_id))
        # El enlace de la vista del participante se entrega solo aquí.
        return {"session_id": run.session_id, "phase": run.phase.value, "view_token": token}

    @router.post("/guided-sessions/{session_id}/view-link")
    def view_link(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        return {"view_token": guarded(lambda: service().new_view_link(user, session_id))}

    @router.get("/guided-sessions/{session_id}")
    def state(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return conductor(guarded(lambda: service().conductor_state(user, session_id)))

    @router.post("/guided-sessions/{session_id}/confirm")
    def confirm(session_id: str, request: ConfirmRequest, user: User = Depends(current_user)) -> dict[str, str]:
        run = guarded(lambda: service().confirm(user, session_id, **request.model_dump()))
        return {"phase": run.phase.value}

    @router.post("/guided-sessions/{session_id}/advance")
    def advance(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        return {"phase": guarded(lambda: service().advance(user, session_id)).phase.value}

    @router.post("/guided-sessions/{session_id}/calibration")
    def calibrate(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        return {"phase": guarded(lambda: service().start_calibration(user, session_id)).phase.value}

    @router.post("/guided-sessions/{session_id}/skip")
    def skip(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        return {"phase": guarded(lambda: service().skip(user, session_id)).phase.value}

    @router.post("/guided-sessions/{session_id}/stop")
    def stop(session_id: str, request: StopRequest, user: User = Depends(current_user)) -> dict[str, str]:
        return {"phase": guarded(lambda: service().stop(user, session_id, request.reason)).phase.value}

    @router.post("/guided-sessions/{session_id}/markers", status_code=201)
    def marker(session_id: str, request: MarkerRequest, user: User = Depends(current_user)) -> dict[str, str]:
        item = guarded(lambda: service().add_marker(user, session_id, request.kind, request.note))
        return {"id": item.id, "kind": item.kind.value, "occurred_at": item.occurred_at.isoformat()}

    @router.post("/guided-sessions/{session_id}/verbal-responses", status_code=201)
    def verbal(session_id: str, request: VerbalRequest, user: User = Depends(current_user)) -> dict[str, Any]:
        item = guarded(lambda: service().record_verbal(user, session_id, request.step_index, request.text))
        return {"step_index": item.step_index}

    @router.get("/sessions/{session_id}/guided-results")
    def results(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """Capturas, marcadores y respuestas: quien condujo y su docente."""
        return conductor(guarded(lambda: service().results(user, session_id)))

    # --- Vista del participante (enlace propio) ----------------------------------------

    @router.get("/participant-view/{token}", response_model=ParticipantView)
    def participant_view(token: str) -> ParticipantView:
        data = guarded(lambda: service().participant_state(token))
        return ParticipantView(**{**data, "abstract_notice": ABSTRACT_NOTICE if data["abstract_notice"] else None})

    @router.get("/participant-view/{token}/stimulus", response_class=Response)
    def participant_stimulus(token: str) -> Response:
        """La imagen del estímulo que se muestra ahora (nunca la de un participante)."""
        stimulus_id = guarded(lambda: service().participant_stimulus(token))
        found = stimulus_image(stimulus_id) if stimulus_image else None
        if found is None:
            raise HTTPException(404, "Estímulo no disponible")
        content_type, data = found
        return Response(content=data, media_type=content_type)

    @router.post("/participant-view/{token}/frames")
    async def participant_frame(token: str, request: Request) -> dict[str, bool]:
        """Un cuadro JPEG de la cámara. Solo se confirma la recepción: ningún resultado."""
        data = await request.body()
        if len(data) > MAX_FRAME_BYTES:
            raise HTTPException(413, "El cuadro es demasiado grande")
        frame = decode_frame(data) if decode_frame else None
        await run_in_threadpool(lambda: guarded(lambda: service().receive_frame(token, frame)))
        return {"received": True}

    @router.post("/participant-view/{token}/stop")
    def participant_stop(token: str) -> dict[str, bool]:
        """El participante pide parar: la sesión termina de inmediato."""
        guarded(lambda: service().participant_stop(token))
        return {"stopped": True}

    return router
