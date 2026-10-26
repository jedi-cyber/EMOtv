"""API del aplicativo Android (contrato en docs/mobile-api.md).

No tiene lógica propia de negocio: llama a los mismos servicios que la web
(AuthenticationService y LoginThrottle, ProtocolService, QuestionnaireService,
el iniciador de sesiones y GuidedSessionService, con can_access_session). No se
registra a las personas evaluadas: cada sesión lleva un código aleatorio. En el
aplicativo, quien conduce y la cámara están en el mismo dispositivo, que también
ve la persona evaluada: por eso ninguna respuesta incluye expresiones estimadas
ni probabilidades.

Todos los errores tienen la forma ``{"detail": {"code": ..., "message": ...}}``.
En producción se rechazan las peticiones que no llegan por HTTPS.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from emotv.application.audit_service import AuditService
from emotv.application.guided_session_service import (
    FRAME_INTERVAL_MS,
    GuidedConflict,
    GuidedNotFound,
    GuidedSessionService,
)
from emotv.application.mobile_auth_service import MobileAuthService, MobileLoginError, MobileTokens
from emotv.application.ports import UserRepository
from emotv.application.protocol_service import ProtocolNotFound, ProtocolService, ProtocolUnavailable
from emotv.application.questionnaire_service import QuestionnaireNotFound, QuestionnaireService
from emotv.application.session_service import SessionService
from emotv.application.signed_urls import StimulusUrlSigner
from emotv.domain import SessionType, User
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.guided_session import ABSTRACT_NOTICE
from emotv.interfaces.web.auth_router import client_ip
from emotv.interfaces.web.guided_router import MAX_FRAME_BYTES
from emotv.interfaces.web.session_router import CONFIRMATIONS, REQUIRED_HEADER, CreateSessionRequest

CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict",
         413: "too_large", 415: "unsupported_media_type", 422: "invalid", 428: "commitment_required",
         429: "too_many_requests", 503: "unavailable"}
ROLE_NAMES = {"student": "Usuario", "psychologist": "Docente"}
COMMITMENT_REMINDER = ("Recuerda tu compromiso de confidencialidad: los datos de la sesión son solo para tu práctica "
                       "y la de tu docente.")
def fail(status: int, message: str, code: str | None = None, headers: dict[str, str] | None = None) -> HTTPException:
    return HTTPException(status, {"code": code or CODES.get(status, "error"), "message": message}, headers=headers)


# --- Cuerpos -------------------------------------------------------------------------

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1, max_length=256)


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Con protocolo, su público decide y no se pregunta nada más.
    protocol_id: str | None = Field(default=None, min_length=1, max_length=64)
    # Sin protocolo: ¿con quién es la sesión? (propia, adulto o infantil).
    session_type: Literal["propia", "adulto", "infantil"] | None = None
    # La única confirmación, según el público (GET /mobile/protocols la devuelve).
    authorization_confirmed: bool = False
    # Versión del aviso sobre datos de menores, la primera vez con un niño o una niña.
    child_notice_version: str | None = Field(default=None, max_length=32)


class AnswersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, Any]
    # La persona responde en el dispositivo, o quien conduce anota lo que dijo.
    entry_mode: Literal["participant", "conductor"] = "participant"


class StopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["participant", "guardian", "conductor"]


def create_mobile_router(
    mobile_auth: MobileAuthService | None,
    users: UserRepository | None,
    *,
    audit: AuditService | None = None,
    sessions: SessionService | None = None,
    start_session: Callable[[User, CreateSessionRequest], Any] | None = None,
    protocols: ProtocolService | None = None,
    questionnaires: QuestionnaireService | None = None,
    guided: GuidedSessionService | None = None,
    signer: StimulusUrlSigner | None = None,
    stimulus_image: Callable[[str], tuple[str, bytes] | None] | None = None,
    decode_frame: Callable[[bytes], Any] | None = None,
    production: bool = False,
    api_version: str = "",
    min_app_version: str = "1.0.0",
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    now = clock or (lambda: datetime.now(timezone.utc))

    def require_https(request: Request) -> None:
        # Detrás del proxy, uvicorn (--proxy-headers) resuelve el esquema de X-Forwarded-Proto.
        if production and request.url.scheme != "https":
            raise fail(403, "El aplicativo debe conectarse por HTTPS", "https_required")

    router = APIRouter(prefix="/mobile", tags=["mobile"], dependencies=[Depends(require_https)])
    bearer = HTTPBearer(auto_error=False)

    def auth_service() -> MobileAuthService:
        if mobile_auth is None:
            raise fail(503, "El inicio de sesión del aplicativo no está disponible")
        return mobile_auth

    def current(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> tuple[User, str]:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise fail(401, "Inicia sesión", "unauthorized", {"WWW-Authenticate": "Bearer"})
        try:
            return auth_service().authenticate_access(credentials.credentials)
        except PermissionError as error:
            raise fail(401, "La sesión venció o se cerró", "invalid_token", {"WWW-Authenticate": "Bearer"}) from error

    def current_user(found: tuple[User, str] = Depends(current)) -> User:
        return found[0]

    def guided_service() -> GuidedSessionService:
        if guided is None or start_session is None or sessions is None:
            raise fail(503, "Las sesiones no están disponibles en este servidor")
        return guided

    def guarded(operation):
        """Traduce las excepciones de los servicios al formato de error del contrato."""
        try:
            return operation()
        except HTTPException as error:
            if isinstance(error.detail, dict):
                raise
            code = "child_notice_required" if (error.headers or {}).get(REQUIRED_HEADER) == "child_notice" else None
            raise fail(error.status_code, str(error.detail), code) from error
        except (GuidedNotFound, ProtocolNotFound, QuestionnaireNotFound) as error:
            raise fail(404, "No encontrado") from error
        except PermissionError as error:
            raise fail(403, str(error)) from error
        except (GuidedConflict, ProtocolUnavailable, RuntimeError) as error:
            raise fail(409, str(error)) from error
        except ValueError as error:
            raise fail(422, str(error)) from error

    def tokens_body(tokens: MobileTokens) -> dict[str, Any]:
        return {"access_token": tokens.access_token, "token_type": "bearer", "expires_in": tokens.expires_in,
                "refresh_token": tokens.refresh_token, "refresh_expires_in": tokens.refresh_expires_in,
                "user": {"id": tokens.user.id, "email": tokens.user.email, "role": tokens.user.role.value,
                         "role_name": ROLE_NAMES.get(tokens.user.role.value, "")}}

    # --- Estado y autenticación ------------------------------------------------------

    @router.get("/status")
    def status() -> dict[str, Any]:
        """Pantalla de carga: no requiere sesión ni devuelve datos personales."""
        return {"status": "ok", "api_version": api_version, "min_app_version": min_app_version,
                "server_time": now().isoformat(),
                "services": {"login": mobile_auth is not None, "sessions": guided is not None}}

    @router.post("/auth/login")
    def login(body: LoginRequest, request: Request) -> dict[str, Any]:
        try:
            tokens = auth_service().login(body.email, body.password, client_ip(request))
        except MobileLoginError as error:
            headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
            raise fail(error.status_code, error.message, error.code, headers) from error
        return tokens_body(tokens)

    @router.post("/auth/refresh")
    def refresh(body: RefreshRequest) -> dict[str, Any]:
        try:
            return tokens_body(auth_service().refresh(body.refresh_token))
        except MobileLoginError as error:
            raise fail(error.status_code, error.message, error.code) from error

    @router.post("/auth/logout", status_code=204)
    def logout(found: tuple[User, str] = Depends(current)) -> Response:
        auth_service().logout(*found)
        return Response(status_code=204)

    # --- Resumen del dashboard ---------------------------------------------------------

    def day_window(day: date | None, offset_minutes: int) -> tuple[date, datetime, datetime]:
        zone = timezone(timedelta(minutes=offset_minutes))
        local_day = day or now().astimezone(zone).date()
        start = datetime(local_day.year, local_day.month, local_day.day, tzinfo=zone)
        return local_day, start, start + timedelta(days=1)

    def session_item(session) -> dict[str, Any]:
        run = guided.repository.get_run(session.id) if guided is not None else None
        protocol = protocols.repository.get(session.protocol_id) if protocols and session.protocol_id else None
        return {"id": session.id, "code": session.code, "started_at": session.started_at.isoformat(),
                "state": session.state.value, "audience": SessionType(session.session_type).value,
                "guided_phase": run.phase.value if run else None,
                "protocol_name": protocol.name if protocol else None}

    def protocol_item(item) -> dict[str, Any]:
        audience = SessionType.CHILD.value if item.for_children else SessionType.ADULT.value
        return {"id": item.id, "name": item.name, "version": item.version,
                "for_children": item.for_children, "audience": audience, "step_count": len(item.steps),
                "has_pre_questionnaire": item.pre_questionnaire_id is not None,
                "has_post_questionnaire": item.post_questionnaire_id is not None,
                "confirmation": CONFIRMATIONS[audience]}

    def usable_for(user: User) -> list[dict[str, Any]]:
        if protocols is None:
            return []
        usable = []
        for item in guarded(lambda: protocols.list_for(user)):
            try:
                protocols.require_usable(user, item.id)
            except (PermissionError, ProtocolUnavailable, ProtocolNotFound, ValueError):
                continue
            usable.append(protocol_item(item))
        return usable

    @router.get("/summary")
    def summary(day: date | None = Query(default=None, alias="date"),
                utc_offset_minutes: int = Query(default=-300, ge=-720, le=840),
                limit: int = Query(default=10, ge=1, le=50),
                user: User = Depends(current_user)) -> dict[str, Any]:
        """Solo lo de la cuenta que inició sesión: sus sesiones recientes y los
        protocolos que puede aplicar, aunque sea docente (lo de su grupo se
        revisa en la web)."""
        guided_service()
        local_day, start, end = day_window(day, utc_offset_minutes)
        owned = sorted(sessions.list_sessions_by_owner(user.id), key=lambda item: item.started_at, reverse=True)
        if audit is not None:
            audit.record(user, AuditAction.VIEW, "mobile_summary", None)
        return {
            "user": {"id": user.id, "email": user.email, "role": user.role.value,
                     "role_name": ROLE_NAMES.get(user.role.value, "")},
            "date": local_day.isoformat(),
            "today_sessions": [session_item(item) for item in owned if start <= item.started_at < end],
            "recent_sessions": [session_item(item) for item in owned[:limit]],
            "protocols": usable_for(user),
            # Sin protocolo se pregunta con quién es la sesión; cada público tiene su confirmación.
            "audiences": [{"value": value, "confirmation": text} for value, text in CONFIRMATIONS.items()],
        }

    # --- Sesión desde el móvil ---------------------------------------------------------

    @router.get("/protocols")
    def usable_protocols(user: User = Depends(current_user)) -> list[dict[str, Any]]:
        """Protocolos que quien inició sesión puede aplicar, con su público y su confirmación."""
        guided_service()
        if protocols is None:
            raise fail(503, "Los protocolos no están configurados")
        return usable_for(user)

    @router.post("/sessions", status_code=201)
    def start(body: StartRequest, user: User = Depends(current_user)) -> dict[str, Any]:
        """Inicia la sesión con la confirmación según el público. Con protocolo sigue
        sus pasos; sin protocolo, calibración y lectura en vivo hasta /finish."""
        service = guided_service()
        request = CreateSessionRequest(protocol_id=body.protocol_id, session_type=body.session_type,
                                       authorization_confirmed=body.authorization_confirmed,
                                       child_notice_version=body.child_notice_version)
        session = guarded(lambda: start_session(user, request))
        try:
            # El enlace de la pantalla de la persona no se usa: este dispositivo muestra los estímulos.
            run, _ = service.create(user, session.id)
        except Exception:
            sessions.cancel_session(session.id)
            raise
        return {"session_id": session.id, "code": session.code, "phase": run.phase.value,
                "audience": SessionType(session.session_type).value, "has_protocol": session.protocol_id is not None,
                "reminder": COMMITMENT_REMINDER}

    @router.get("/sessions/{session_id}/next")
    def next_step(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """Qué mostrar ahora: cuestionario, calibración, estímulo, lectura en vivo o fin."""
        service = guided_service()
        state = guarded(lambda: service.conductor_state(user, session_id))
        phase = state["phase"]
        body: dict[str, Any] = {"session_id": session_id, "code": state["session_code"], "phase": phase,
                                "stop_reason": state["stop_reason"],
                                "send_frames": False, "frame_interval_ms": FRAME_INTERVAL_MS,
                                "capture_status": state["capture_status"], "questionnaire": None,
                                "calibration": None, "stimulus": None,
                                "step_count": state["step_count"]}
        if phase in ("pre_questionnaire", "post_questionnaire"):
            moment = phase.split("_")[0]
            item = guarded(lambda: questionnaires.pending_for(user, session_id, moment))
            body["questionnaire"] = {
                "moment": moment, "id": item.id, "version": item.version, "title": item.title,
                "instructions": item.instructions, "questions": [question.to_dict() for question in item.questions],
                "answered": questionnaires.answered(session_id, moment)}
        elif phase == "calibration":
            body["calibration"] = state["calibration"]
            body["send_frames"] = state["calibration"]["state"] == "calibrating"
        elif phase == "live":
            # Sin protocolo: solo la lectura de la expresión, hasta que quien conduce termina.
            body["send_frames"] = True
        elif phase in ("before_analyzer", "stimuli"):
            step = state["steps"][state["step_index"]]
            expires, signature = signer.sign(user.id, session_id, step["stimulus_id"])
            body["stimulus"] = {
                "step_index": step["index"], "title": step["title"], "kind": step["kind"],
                "exposure_seconds": step["exposure_seconds"], "remaining_seconds": state["remaining_seconds"],
                "image_url": (f"/mobile/stimulus-images/{session_id}/{step['stimulus_id']}"
                              f"?expires={expires}&signature={signature}"),
                "image_expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
                "abstract_notice": ABSTRACT_NOTICE if step["kind"] == "abstract" else None,
                # Lo registra quien conduce desde la web.
                "records_verbal_response": step["record_verbal_response"]}
            body["send_frames"] = phase == "stimuli"
        return body

    @router.post("/sessions/{session_id}/questionnaires/{moment}", status_code=201)
    def answer(session_id: str, moment: Literal["pre", "post"], body: AnswersRequest,
               user: User = Depends(current_user)) -> dict[str, Any]:
        """Guarda las respuestas (cifradas) y continúa a la fase siguiente."""
        service = guided_service()
        if questionnaires is None:
            raise fail(503, "Los cuestionarios no están disponibles")
        guarded(lambda: questionnaires.submit(user, session_id, moment, body.answers, body.entry_mode))
        run = guarded(lambda: service.advance(user, session_id))
        return {"phase": run.phase.value}

    @router.post("/sessions/{session_id}/advance")
    def advance(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return {"phase": guarded(lambda: guided_service().advance(user, session_id)).phase.value}

    @router.post("/sessions/{session_id}/calibration")
    def calibration(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return {"phase": guarded(lambda: guided_service().start_calibration(user, session_id)).phase.value}

    @router.post("/sessions/{session_id}/frames")
    async def frame(session_id: str, request: Request, user: User = Depends(current_user)) -> dict[str, Any]:
        """Un cuadro JPEG. Se analiza en memoria con el modelo local y se descarta."""
        service = guided_service()
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "image/jpeg":
            raise fail(415, "Envía el cuadro como image/jpeg")
        data = await request.body()
        if len(data) > MAX_FRAME_BYTES:
            raise fail(413, "El cuadro es demasiado grande")
        decoded = decode_frame(data) if decode_frame else None
        if decoded is None:
            raise fail(422, "El cuadro no es una imagen JPEG válida")
        return await run_in_threadpool(lambda: guarded(lambda: service.conductor_frame(user, session_id, decoded)))

    @router.post("/sessions/{session_id}/skip")
    def skip(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return {"phase": guarded(lambda: guided_service().skip(user, session_id)).phase.value}

    @router.post("/sessions/{session_id}/finish")
    def finish(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """Termina una sesión sin protocolo (fase live) y devuelve su código."""
        run = guarded(lambda: guided_service().finish_live(user, session_id))
        session = sessions.get_session(session_id)
        return {"phase": run.phase.value, "code": session.code if session else None}

    @router.post("/sessions/{session_id}/stop")
    def stop(session_id: str, body: StopRequest, user: User = Depends(current_user)) -> dict[str, Any]:
        """Interrumpe la sesión: la persona, su tutor o quien conduce lo pidió."""
        return {"phase": guarded(lambda: guided_service().stop(user, session_id, body.reason)).phase.value}

    # --- Imágenes de estímulos (URL firmada) ----------------------------------------------

    @router.get("/stimulus-images/{session_id}/{stimulus_id}", response_class=Response)
    def stimulus(session_id: str, stimulus_id: str, expires: int, signature: str) -> Response:
        """Sin token: la firma nombra la sesión, el estímulo y el vencimiento, y solo
        vale mientras la sesión de quien la recibió sigue activa con ese protocolo."""
        service = guided_service()
        run = service.repository.get_run(session_id)
        owner = users.get_by_id(run.owner_user_id) if run is not None and users is not None else None
        valid = (owner is not None and signer is not None
                 and signer.verify(owner.id, session_id, stimulus_id, expires, signature)
                 and service.stimulus_in_active_session(owner.id, session_id, stimulus_id))
        if audit is not None:
            audit.record(owner, AuditAction.VIEW, "stimulus_image", stimulus_id,
                         AuditResult.SUCCESS if valid else AuditResult.DENIED)
        if not valid:
            raise fail(403, "El enlace de la imagen venció o no es válido", "invalid_or_expired_url")
        found = stimulus_image(stimulus_id) if stimulus_image else None
        if found is None:
            raise fail(404, "Estímulo no disponible")
        content_type, data = found
        return Response(content=data, media_type=content_type)

    return router
