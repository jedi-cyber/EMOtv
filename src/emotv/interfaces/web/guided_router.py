"""Sesión con protocolo: rutas de quien conduce y de la pantalla de la persona.

La pantalla de la persona evaluada usa un enlace propio (sin cuenta) y solo recibe lo
que debe mostrar: nunca expresiones, probabilidades, calidad ni notas. Los
cuadros de su cámara se analizan en memoria y se descartan.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from emotv.application import AuthenticationService
from emotv.application.guided_session_service import GuidedConflict, GuidedNotFound, GuidedSessionService
from emotv.application.ports import UserRepository
from emotv.domain import User
from emotv.domain.guided_session import ABSTRACT_NOTICE, MAX_NOTE_LENGTH, PAIRING_SECONDS
from emotv.interfaces.web.auth_router import create_current_user_dependency

MAX_FRAME_BYTES = 1_000_000


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


class PracticeFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visible: bool


class RecognitionAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str = Field(min_length=1, max_length=32)


class GameActionRequest(BaseModel):
    """Una acción de un juego: elegir una opción, pedir ayuda o pasar de ronda.
    expression es la clave de la opción: la emoción al emparejar con nombres, el
    lugar («1», «2»…) al buscar la misma emoción."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["answer", "help", "next"]
    expression: str | None = Field(default=None, min_length=1, max_length=32)


class CameraProblemRequest(BaseModel):
    reason: str = Field(max_length=16)


class RecognitionOption(BaseModel):
    key: str
    label: str


class RecognitionView(BaseModel):
    """Un paso de reconocimiento: la pregunta, las opciones y, al terminar, el
    nombre de la emoción de la imagen. Nunca la expresión detectada."""

    question: str
    # Historia corta del paso, si la tiene.
    situation: str | None = None
    options: list[RecognitionOption]
    chosen: str | None
    message: str | None
    # Al terminar el paso: explicación sencilla de la emoción de la imagen y, con
    # una situación, que cada persona puede sentir algo distinto.
    explanation: str | None = None
    note: str | None = None


class DrawingView(BaseModel):
    """Un paso de dibujo: la consigna, la pregunta y las emociones para señalar.
    El dibujo se queda en la pantalla de la persona; aquí solo vuelve la emoción
    que eligió, sin compararla con el dibujo."""

    instruction: str
    question: str
    options: list[RecognitionOption]
    # Cambia con cada intento: la pantalla empieza un lienzo nuevo.
    round: str
    finished: bool
    chosen: str | None
    message: str | None


class GameOption(BaseModel):
    key: str
    label: str
    # Falso si ya la eligió en esta ronda o la quitó la ayuda.
    available: bool


class GameView(BaseModel):
    """Una ronda del juego de emparejar: la pregunta, las emociones para tocar y,
    al terminar la ronda, la de la imagen con su explicación. Sin puntaje."""

    round: str
    number: int
    total: int
    # matching (nombres) o similar (imágenes: cada opción se pide por su clave).
    game_type: str = "matching"
    question: str
    # playing, retry, matched, shown, finished o ended (venció el tiempo).
    state: str
    options: list[GameOption]
    answer: str | None
    message: str | None
    explanation: str | None = None
    can_help: bool
    last_round: bool


class PracticeView(BaseModel):
    """Un ejercicio de práctica: instrucción, nivel de 0 a 1 (nulo si la señal
    está apagada) y si se logró. Nunca la expresión detectada ni probabilidades."""

    instruction: str
    level: float | None = Field(default=None, ge=0, le=1)
    achieved: bool
    message: str | None
    frame_interval_ms: int


class ParticipantView(BaseModel):
    """Lo único que recibe la pantalla de la persona evaluada."""

    phase: str
    message: str | None
    stimulus: dict[str, str] | None
    remaining_seconds: float | None
    capture_frames: bool
    frame_interval_ms: int
    abstract_notice: str | None
    practice: PracticeView | None = None
    recognition: RecognitionView | None = None
    drawing: DrawingView | None = None
    game: GameView | None = None
    # Modo accesible del protocolo: pictogramas, botones grandes y sin animaciones.
    accessible: bool = False
    # Falso en un protocolo solo de reconocimientos: la pantalla no pide la cámara.
    uses_camera: bool = True
    # Apoyos que cambian la pantalla (pictogramas, botones grandes, lectura en voz
    # alta); solo aparece si el protocolo tiene alguno.
    supports: dict[str, bool] | None = None
    # La actividad de ahora (tipo, nombre y paso), sin respuestas; la usa Android.
    activity: dict[str, Any] | None = None


def create_guided_router(
    guided: GuidedSessionService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    stimulus_image=None,       # Callable[[str], tuple[str, bytes] | None]
    decode_frame=None,         # Callable[[bytes], ndarray | None]
    capacity=None,             # AnalysisCapacity: cupo de análisis de los cuadros de práctica
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
        # El enlace de la pantalla de la persona se entrega solo aquí.
        return {"session_id": run.session_id, "phase": run.phase.value, "view_token": token}

    @router.post("/guided-sessions/{session_id}/view-link")
    def view_link(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        return {"view_token": guarded(lambda: service().new_view_link(user, session_id))}

    @router.post("/guided-sessions/{session_id}/android-code")
    def android_code(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """Código de un solo uso para abrir la pantalla de la persona en Android.
        Se entrega solo aquí; al canjearlo, el enlace anterior deja de valer."""
        code, expires = guarded(lambda: service().new_android_code(user, session_id))
        return {"code": code, "expires_at": expires.isoformat(), "expires_in": PAIRING_SECONDS}

    @router.get("/guided-sessions/{session_id}")
    def state(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return conductor(guarded(lambda: service().conductor_state(user, session_id)))

    @router.post("/guided-sessions/{session_id}/advance")
    def advance(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        return {"phase": guarded(lambda: service().advance(user, session_id)).phase.value}

    @router.post("/guided-sessions/{session_id}/start")
    def start(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        """Empieza el primer paso de una sesión sin cámara."""
        return {"phase": guarded(lambda: service().start(user, session_id)).phase.value}

    @router.post("/guided-sessions/{session_id}/continue")
    def continue_after_pause(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        """«Seguir»: con la pausa «esperar a quien conduce», pasa al paso siguiente."""
        return {"phase": guarded(lambda: service().continue_after_pause(user, session_id)).phase.value}

    @router.post("/guided-sessions/{session_id}/repeat")
    def repeat_step(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        """«Repetir este paso»: el reconocimiento o el ejercicio que acaba de terminar empieza otra vez."""
        return {"phase": guarded(lambda: service().repeat_step(user, session_id)).phase.value}

    @router.post("/guided-sessions/{session_id}/continue-without-camera")
    def continue_without_camera(session_id: str, user: User = Depends(current_user)) -> dict[str, str]:
        """La cámara no está disponible: siguen los pasos que no la necesitan."""
        return {"phase": guarded(lambda: service().continue_without_camera(user, session_id)).phase.value}

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

    @router.post("/guided-sessions/{session_id}/practice-feedback")
    def practice_feedback(session_id: str, request: PracticeFeedbackRequest,
                          user: User = Depends(current_user)) -> dict[str, bool]:
        """Enciende o apaga la señal del nivel en la pantalla de la persona."""
        run = guarded(lambda: service().set_practice_feedback(user, session_id, request.visible))
        return {"practice_feedback": run.practice_feedback}

    @router.post("/guided-sessions/{session_id}/recognition")
    def recognition(session_id: str, request: RecognitionAnswerRequest,
                    user: User = Depends(current_user)) -> dict[str, str]:
        """Quien conduce registra la opción que la persona señaló o dijo."""
        run = guarded(lambda: service().record_recognition(user, session_id, request.expression))
        return {"phase": run.phase.value}

    @router.post("/guided-sessions/{session_id}/game")
    def game(session_id: str, request: GameActionRequest, user: User = Depends(current_user)) -> dict[str, str]:
        """Quien conduce registra la emoción que la persona señaló, pide la ayuda o pasa de ronda."""
        run = guarded(lambda: service().conductor_game(user, session_id, request.action, request.expression))
        return {"phase": run.phase.value}

    @router.post("/guided-sessions/{session_id}/verbal-responses", status_code=201)
    def verbal(session_id: str, request: VerbalRequest, user: User = Depends(current_user)) -> dict[str, Any]:
        item = guarded(lambda: service().record_verbal(user, session_id, request.step_index, request.text))
        return {"step_index": item.step_index}

    @router.get("/sessions/{session_id}/guided-results")
    def results(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """Capturas, marcadores y respuestas: quien condujo y su docente."""
        return conductor(guarded(lambda: service().results(user, session_id)))

    # --- Pantalla de la persona evaluada (enlace propio) ----------------------------------------

    @router.get("/participant-view/{token}")
    def participant_view(token: str) -> dict[str, Any]:
        data = guarded(lambda: service().participant_state(token))
        view = ParticipantView(**{**data, "abstract_notice": ABSTRACT_NOTICE if data["abstract_notice"] else None})
        # practice, recognition, drawing y game solo aparecen en su paso, accessible solo si el protocolo
        # lo activa y uses_camera solo cuando es falso: las sesiones con cámara quedan como antes.
        hidden = {name for name in ("practice", "recognition", "drawing", "game") if getattr(view, name) is None}
        hidden |= set() if view.accessible else {"accessible"}
        hidden |= {"uses_camera"} if view.uses_camera else set()
        hidden |= {"supports"} if view.supports is None else set()
        # Una estación de examen no recibe la actividad: no sabe qué se mide.
        hidden |= {"activity"} if view.activity is None else set()
        return view.model_dump(exclude=hidden)

    @router.get("/participant-view/{token}/stimulus", response_class=Response)
    def participant_stimulus(token: str) -> Response:
        """La imagen del estímulo que se muestra ahora (nunca la de una persona evaluada)."""
        stimulus_id = guarded(lambda: service().participant_stimulus(token))
        found = stimulus_image(stimulus_id) if stimulus_image else None
        if found is None:
            raise HTTPException(404, "Estímulo no disponible")
        content_type, data = found
        return Response(content=data, media_type=content_type)

    @router.get("/participant-view/{token}/game/option/{key}", response_class=Response)
    def participant_game_option(token: str, key: str = Path(min_length=1, max_length=8)) -> Response:
        """La imagen de una opción de la ronda en curso de «Busca la misma emoción»."""
        stimulus_id = guarded(lambda: service().participant_game_option(token, key))
        found = stimulus_image(stimulus_id) if stimulus_image else None
        if found is None:
            raise HTTPException(404, "Estímulo no disponible")
        content_type, data = found
        return Response(content=data, media_type=content_type)

    @router.post("/participant-view/{token}/camera-problem")
    def participant_camera_problem(token: str, request: CameraProblemRequest) -> dict[str, bool]:
        """La pantalla de la persona no pudo usar la cámara; solo informa el motivo."""
        guarded(lambda: service().participant_camera_problem(token, request.reason))
        return {"received": True}

    @router.post("/participant-view/{token}/frames")
    async def participant_frame(token: str, request: Request) -> dict[str, bool]:
        """Un cuadro JPEG de la cámara. Solo se confirma la recepción: ningún resultado."""
        data = await request.body()
        if len(data) > MAX_FRAME_BYTES:
            raise HTTPException(413, "El cuadro es demasiado grande")
        frame = decode_frame(data) if decode_frame else None

        def receive() -> None:
            guarded(lambda: service().receive_frame(token, frame))

        practice = capacity is not None and await run_in_threadpool(
            lambda: guarded(lambda: service().practice_frame_drops_when_busy(token)))
        if practice:
            # Cada cuadro de una práctica se analiza dentro del cupo del servidor;
            # sin cupo libre se descarta. La persona no recibe ninguna señal de ello.
            await capacity.try_run(receive)
        else:
            await run_in_threadpool(receive)
        return {"received": True}

    @router.post("/participant-view/{token}/answer")
    def participant_answer(token: str, request: RecognitionAnswerRequest) -> dict[str, bool]:
        """La persona tocó una opción. Solo se confirma la recepción: si acertó
        no se devuelve (la pantalla muestra el nombre de la emoción en su estado)."""
        guarded(lambda: service().participant_answer(token, request.expression))
        return {"received": True}

    @router.post("/participant-view/{token}/game")
    def participant_game(token: str, request: GameActionRequest) -> dict[str, bool]:
        """La persona tocó una emoción, «Ayuda» o «Siguiente». Solo se confirma la
        recepción: la pantalla lee lo que pasó en su estado."""
        guarded(lambda: service().participant_game(token, request.action, request.expression))
        return {"received": True}

    @router.post("/participant-view/{token}/stop")
    def participant_stop(token: str) -> dict[str, bool]:
        """La persona pide parar: la sesión termina de inmediato."""
        guarded(lambda: service().participant_stop(token))
        return {"stopped": True}

    return router
