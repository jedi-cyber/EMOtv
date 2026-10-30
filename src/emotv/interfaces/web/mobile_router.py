"""API del aplicativo Android (contrato en docs/mobile-api.md).

El aplicativo no conduce sesiones: ninguna captura del rostro sale del
teléfono. Las sesiones se conducen en la web; el aplicativo consulta las
sesiones, sus reportes y las estadísticas agregadas, y permite actuar sobre el
reporte (el Usuario lo redacta y lo envía; el Docente lo comenta, lo devuelve o
lo aprueba).

No tiene lógica propia de negocio: llama a los mismos servicios que la web
(AuthenticationService y LoginThrottle, SessionInsightsService, ReportService y
SessionStatisticsService), que aplican can_access_session y registran la
auditoría. No se registra a las personas evaluadas: cada sesión se identifica
solo por su código.

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

from emotv.application.audit_service import AuditService
from emotv.application.mobile_auth_service import MobileAuthService, MobileLoginError, MobileTokens
from emotv.application.ports import UserRepository
from emotv.application.report_service import ReportConflict, ReportNotFound, ReportService
from emotv.application.session_insights_service import InsightsNotFound, SessionInsightsService
from emotv.application.session_statistics_service import SessionStatisticsService, StatisticsFilter
from emotv.domain import EmotionalSession, SessionType, User
from emotv.domain.audit import AuditAction
from emotv.domain.report import ReportSection
from emotv.domain.role import Role
from emotv.interfaces.web.auth_router import client_ip

CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict",
         422: "invalid", 429: "too_many_requests", 503: "unavailable"}
ROLE_NAMES = {"student": "Usuario", "psychologist": "Docente"}


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


class NarrativeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    narrative: str = Field(max_length=8000)


class CommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: ReportSection = ReportSection.GENERAL
    text: str = Field(min_length=1, max_length=2000)


def create_mobile_router(
    mobile_auth: MobileAuthService | None,
    users: UserRepository | None,
    *,
    audit: AuditService | None = None,
    visible_sessions: Callable[[User], list[EmotionalSession]] | None = None,
    insights: SessionInsightsService | None = None,
    reports: ReportService | None = None,
    statistics: SessionStatisticsService | None = None,
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

    def session_services() -> tuple[Callable[[User], list[EmotionalSession]], SessionInsightsService]:
        if visible_sessions is None or insights is None:
            raise fail(503, "Las sesiones no están disponibles en este servidor")
        return visible_sessions, insights

    def report_service() -> ReportService:
        if reports is None:
            raise fail(503, "Los reportes no están disponibles en este servidor")
        return reports

    def guarded(operation):
        """Traduce las excepciones de los servicios al formato de error del contrato."""
        try:
            return operation()
        except (InsightsNotFound, ReportNotFound) as error:
            raise fail(404, "No encontrado") from error
        except PermissionError as error:
            raise fail(403, str(error)) from error
        except ReportConflict as error:
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
                "services": {"login": mobile_auth is not None,
                             "sessions": visible_sessions is not None and insights is not None,
                             "reports": reports is not None, "statistics": statistics is not None}}

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

    # --- Sesiones (solo consulta) --------------------------------------------------------

    def session_items(user: User, found: list[EmotionalSession]) -> list[dict[str, Any]]:
        _, service = session_services()
        current_reports = reports.current_for_sessions(tuple(item.id for item in found)) if reports else {}
        items = []
        for session in found:
            protocol = service.protocols(session.protocol_id) if session.protocol_id else None
            report = current_reports.get(session.id)
            items.append({
                "id": session.id, "code": session.code, "started_at": session.started_at.isoformat(),
                "state": session.state.value, "audience": SessionType(session.session_type).value,
                "protocol_name": protocol.name if protocol else None,
                # Del docente: las sesiones de su grupo no son suyas.
                "mine": session.owner_user_id == user.id,
                "report_status": report.status.value if report else None,
            })
        return items

    def newest_first(user: User) -> list[EmotionalSession]:
        listing, _ = session_services()
        return sorted(listing(user), key=lambda item: (item.started_at, item.id), reverse=True)

    def pending_reviews(user: User, found: list[EmotionalSession]) -> list[EmotionalSession]:
        if reports is None or user.role is not Role.PSYCHOLOGIST:
            return []
        waiting = reports.pending_review(user, tuple(item.id for item in found))
        return [item for item in found if item.id in waiting]

    def day_window(day: date | None, offset_minutes: int) -> tuple[date, datetime, datetime]:
        zone = timezone(timedelta(minutes=offset_minutes))
        local_day = day or now().astimezone(zone).date()
        start = datetime(local_day.year, local_day.month, local_day.day, tzinfo=zone)
        return local_day, start, start + timedelta(days=1)

    @router.get("/summary")
    def summary(day: date | None = Query(default=None, alias="date"),
                utc_offset_minutes: int = Query(default=-300, ge=-720, le=840),
                limit: int = Query(default=10, ge=1, le=50),
                user: User = Depends(current_user)) -> dict[str, Any]:
        """Inicio del aplicativo: sesiones de hoy y recientes (las que la cuenta
        ya puede ver en la web) y, para el docente, los reportes por revisar."""
        local_day, start, end = day_window(day, utc_offset_minutes)
        found = newest_first(user)
        if audit is not None:
            audit.record(user, AuditAction.VIEW, "mobile_summary", None)
        return {
            "user": {"id": user.id, "email": user.email, "role": user.role.value,
                     "role_name": ROLE_NAMES.get(user.role.value, "")},
            "date": local_day.isoformat(),
            "today_sessions": session_items(user, [item for item in found if start <= item.started_at < end]),
            "recent_sessions": session_items(user, found[:limit]),
            "pending_reviews": len(pending_reviews(user, found)),
        }

    @router.get("/sessions")
    def list_sessions(limit: int = Query(default=100, ge=1, le=500),
                      user: User = Depends(current_user)) -> list[dict[str, Any]]:
        """Las sesiones de la cuenta y, para el docente, las de su grupo; de la más nueva a la más antigua."""
        found = newest_first(user)[:limit]
        if audit is not None:
            audit.record(user, AuditAction.VIEW, "mobile_sessions", None)
        return session_items(user, found)

    @router.get("/sessions/{session_id}")
    def session_detail(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """Línea de tiempo y métricas descriptivas; el acceso lo decide can_access_session."""
        _, service = session_services()
        timeline = guarded(lambda: service.timeline(user, session_id))
        metrics = guarded(lambda: service.metrics(user, session_id))
        session = service.sessions.get_session(session_id)
        return {"session": session_items(user, [session])[0], "timeline": timeline, "metrics": metrics}

    # --- Reporte ----------------------------------------------------------------------

    @router.get("/sessions/{session_id}/report")
    def session_report(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: report_service().for_session(user, session_id))

    @router.post("/sessions/{session_id}/report", status_code=201)
    def create_report(session_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        """Quien condujo la sesión empieza su reporte (borrador)."""
        service = report_service()
        created = guarded(lambda: service.create(user, session_id))
        return guarded(lambda: service.get(user, created.id))

    def act(user: User, report_id: str, action: Callable[[ReportService], Any]) -> dict[str, Any]:
        """Aplica la acción y devuelve el reporte actualizado, con lo que la cuenta puede hacer ahora."""
        service = report_service()
        guarded(lambda: action(service))
        return guarded(lambda: service.get(user, report_id))

    @router.get("/reports/{report_id}")
    def get_report(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return guarded(lambda: report_service().get(user, report_id))

    @router.put("/reports/{report_id}")
    def edit_report(report_id: str, body: NarrativeRequest, user: User = Depends(current_user)) -> dict[str, Any]:
        """El Usuario responde a las observaciones corrigiendo el texto."""
        return act(user, report_id, lambda service: service.edit(user, report_id, body.narrative))

    @router.post("/reports/{report_id}/submit")
    def submit_report(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return act(user, report_id, lambda service: service.submit(user, report_id))

    @router.post("/reports/{report_id}/comments")
    def comment_report(report_id: str, body: CommentRequest, user: User = Depends(current_user)) -> dict[str, Any]:
        return act(user, report_id, lambda service: service.comment(user, report_id, body.section, body.text))

    @router.post("/reports/{report_id}/return")
    def return_report(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return act(user, report_id, lambda service: service.return_with_comments(user, report_id))

    @router.post("/reports/{report_id}/approve")
    def approve_report(report_id: str, user: User = Depends(current_user)) -> dict[str, Any]:
        return act(user, report_id, lambda service: service.approve(user, report_id))

    @router.get("/reviews")
    def reviews(user: User = Depends(current_user)) -> list[dict[str, Any]]:
        """Del docente: reportes que los usuarios de su grupo enviaron a revisión."""
        if user.role is not Role.PSYCHOLOGIST:
            raise fail(403, "Solo el docente revisa reportes")
        report_service()
        waiting = pending_reviews(user, newest_first(user))
        current_reports = reports.current_for_sessions(tuple(item.id for item in waiting))
        if audit is not None:
            audit.record(user, AuditAction.VIEW, "mobile_reviews", None)
        return [{**item, "report_id": current_reports[item["id"]].id} for item in session_items(user, waiting)]

    # --- Estadísticas agregadas ---------------------------------------------------------

    @router.get("/statistics")
    def session_statistics(scope: Literal["mine", "group"] = "mine",
                           date_from: date | None = None,
                           date_to: date | None = None,
                           user: User = Depends(current_user)) -> dict[str, Any]:
        """Cuentan sesiones, no personas. En el aplicativo no se desglosa por usuario."""
        if statistics is None:
            raise fail(503, "Las estadísticas no están disponibles en este servidor")
        if date_from and date_to and date_from > date_to:
            raise fail(422, "La fecha inicial es posterior a la final")
        result = guarded(lambda: statistics.statistics(user, StatisticsFilter(
            scope=scope, date_from=date_from, date_to=date_to)))
        return {key: result[key] for key in ("scope", "notice", "few_sessions_notice", "sessions", "expressions",
                                             "coincidence")}

    return router
