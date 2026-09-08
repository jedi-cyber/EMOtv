from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from emotv.application import AuthenticationService, AuthorizationService, SessionService
from emotv.application.ports import StudentRepository, UserRepository
from emotv.domain import AccessAction, EmotionalSession, Role, User
from emotv.interfaces.web.auth_router import create_current_user_dependency


class CreateSessionRequest(BaseModel):
    student_id: str | None = None


class SessionResponse(BaseModel):
    id: str
    state: str
    student_id: str | None
    started_at: datetime
    completed_at: datetime | None
    initial_emotion: str | None
    emotion_confidence: float | None
    activity_id: str | None
    exercise_result: str | None
    exercise_duration_seconds: float | None

    @classmethod
    def from_domain(cls, session: EmotionalSession) -> "SessionResponse":
        return cls(id=session.id, state=session.state.value,
                   student_id=session.student_id, started_at=session.started_at,
                   completed_at=session.completed_at,
                   initial_emotion=session.initial_emotion,
                   emotion_confidence=session.emotion_confidence,
                   activity_id=session.activity_id,
                   exercise_result=session.exercise_result,
                   exercise_duration_seconds=session.exercise_duration_seconds)


def create_session_router(
    sessions: SessionService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    students: StudentRepository | None,
    authorization: AuthorizationService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/sessions", tags=["sessions"])
    policy = authorization or AuthorizationService()
    current_user = create_current_user_dependency(authentication, users)

    def services() -> tuple[SessionService, StudentRepository]:
        if sessions is None or students is None:
            raise HTTPException(status_code=503, detail="Sesiones no configuradas")
        return sessions, students

    def target_student(user: User, requested: str | None) -> tuple[str | None, str | None]:
        _, student_repository = services()
        if user.role is not Role.STUDENT:
            return requested, None
        actor = student_repository.get_by_user_id(user.id)
        if actor is None:
            raise HTTPException(status_code=403, detail="Perfil estudiantil no encontrado")
        return requested or actor.id, actor.id

    @router.post("", response_model=SessionResponse, status_code=201)
    def start(request: CreateSessionRequest, user: User = Depends(current_user)) -> SessionResponse:
        service, _ = services()
        resource_id, actor_id = target_student(user, request.student_id)
        try:
            policy.require(user, AccessAction.START_SESSION,
                           resource_student_id=resource_id, actor_student_id=actor_id)
            session = service.start_session(student_id=resource_id)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        return SessionResponse.from_domain(session)

    @router.post("/{session_id}/cancel", response_model=SessionResponse)
    def cancel(session_id: str, user: User = Depends(current_user)) -> SessionResponse:
        service, student_repository = services()
        session = service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        actor = student_repository.get_by_user_id(user.id) if user.role is Role.STUDENT else None
        try:
            policy.require(user, AccessAction.CANCEL_SESSION,
                           resource_student_id=session.student_id,
                           actor_student_id=actor.id if actor else None)
            cancelled = service.cancel_session(session.id)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return SessionResponse.from_domain(cancelled)

    @router.get("/{session_id}", response_model=SessionResponse)
    def get_by_id(session_id: str, user: User = Depends(current_user)) -> SessionResponse:
        service, student_repository = services()
        session = service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        actor = student_repository.get_by_user_id(user.id) if user.role is Role.STUDENT else None
        try:
            policy.require(user, AccessAction.VIEW_SESSION,
                           resource_student_id=session.student_id,
                           actor_student_id=actor.id if actor else None)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        return SessionResponse.from_domain(session)

    @router.get("", response_model=list[SessionResponse])
    def list_sessions(
        student_id: str | None = None,
        user: User = Depends(current_user),
    ) -> list[SessionResponse]:
        service, student_repository = services()
        actor = student_repository.get_by_user_id(user.id) if user.role is Role.STUDENT else None
        resource_id = student_id
        if user.role is Role.STUDENT:
            if actor is None:
                raise HTTPException(status_code=403, detail="Perfil estudiantil no encontrado")
            resource_id = student_id or actor.id
        try:
            policy.require(user, AccessAction.LIST_STUDENT_SESSIONS,
                           resource_student_id=resource_id,
                           actor_student_id=actor.id if actor else None)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        sessions_found = (
            service.list_sessions()
            if resource_id is None
            else service.list_sessions_by_student(resource_id)
        )
        return [SessionResponse.from_domain(item) for item in sessions_found]

    return router
