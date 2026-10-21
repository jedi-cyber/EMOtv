from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from emotv.application import ActivityCatalog, AuthenticationService, AuthorizationService, SessionService
from emotv.application.ports import StudentRepository, UserRepository
from emotv.application.ports.assignment_repository import AssignmentRepository
from emotv.domain import AccessAction, EmotionalSession, Role, SessionType, User
from emotv.interfaces.web.auth_router import create_current_user_dependency
from emotv.application.commitment_service import CommitmentRequired, CommitmentService


SessionTypeValue = Literal["propia", "participante_adulto", "participante_infantil"]
# Una sesión con participante requiere registrar al participante y su
# autorización firmada; hasta que ese registro exista no se pueden iniciar.
PARTICIPANT_SESSIONS_UNAVAILABLE = (
    "Las sesiones con participante requieren registrar al participante y su autorización firmada, "
    "que todavía no están disponibles. Inicia una sesión propia."
)


class CreateSessionRequest(BaseModel):
    student_id: str | None = None
    activity_id: str | None = None
    session_type: SessionTypeValue = SessionType.OWN.value


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
    emotion_model_id: str | None
    emotion_model_version: str | None
    recognized_at: datetime | None = None
    exercise_steps_completed: int | None = None
    exercise_steps_total: int | None = None
    exercise_repetitions: int | None = None
    session_type: SessionTypeValue = SessionType.OWN.value
    # Cuenta que conduce la sesión: solo ella puede cancelarla.
    owner_user_id: str | None = None

    @classmethod
    def from_domain(cls, session: EmotionalSession) -> "SessionResponse":
        return cls(id=session.id, state=session.state.value,
                   student_id=session.student_id, started_at=session.started_at,
                   completed_at=session.completed_at,
                   initial_emotion=session.initial_emotion,
                   emotion_confidence=session.emotion_confidence,
                   activity_id=session.activity_id,
                   exercise_result=session.exercise_result,
                   exercise_duration_seconds=session.exercise_duration_seconds,
                   emotion_model_id=session.emotion_model_id,
                   emotion_model_version=session.emotion_model_version,
                   recognized_at=session.recognized_at,
                   exercise_steps_completed=session.exercise_steps_completed,
                   exercise_steps_total=session.exercise_steps_total,
                   exercise_repetitions=session.exercise_repetitions,
                   session_type=SessionType(session.session_type).value,
                   owner_user_id=session.owner_user_id)


def create_session_router(
    sessions: SessionService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    students: StudentRepository | None,
    authorization: AuthorizationService | None = None,
    activities: ActivityCatalog | None = None,
    assignments: AssignmentRepository | None = None,
    commitments: CommitmentService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/sessions", tags=["sessions"])
    policy = authorization or AuthorizationService()
    current_user = create_current_user_dependency(authentication, users)

    def services() -> tuple[SessionService, StudentRepository]:
        if sessions is None or students is None:
            raise HTTPException(status_code=503, detail="Sesiones no configuradas")
        return sessions, students

    def actor_student_id(user: User) -> str | None:
        _, student_repository = services()
        actor = student_repository.get_by_user_id(user.id) if user.role is Role.STUDENT else None
        return actor.id if actor else None

    def require_session_access(user: User, session: EmotionalSession) -> None:
        # El administrador y el superadministrador nunca acceden a sesiones.
        if not policy.can_access_session(user, session, actor_student_id=actor_student_id(user)):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta sesión")

    @router.post("", response_model=SessionResponse, status_code=201)
    def start(request: CreateSessionRequest, user: User = Depends(current_user)) -> SessionResponse:
        service, student_repository = services()
        if request.session_type != SessionType.OWN.value:
            raise HTTPException(status_code=422, detail=PARTICIPANT_SESSIONS_UNAVAILABLE)
        if user.role is Role.STUDENT:
            actor = student_repository.get_by_user_id(user.id)
            if actor is None:
                raise HTTPException(status_code=403, detail="Tu cuenta de usuario no tiene perfil asociado")
            resource_id, actor_id = request.student_id or actor.id, actor.id
        else:
            # El docente conduce sesiones propias: sin perfil de usuario asociado.
            if request.student_id is not None:
                raise HTTPException(status_code=403, detail="Cada usuario inicia sus sesiones desde su cuenta")
            resource_id, actor_id = None, None
        try:
            if request.activity_id is not None and activities is not None:
                activities.get(request.activity_id)
            policy.require(user, AccessAction.START_SESSION,
                           resource_student_id=resource_id, actor_student_id=actor_id)
            if commitments is not None:
                commitments.require(user)
            session = service.start_session(
                student_id=resource_id,
                activity_id=request.activity_id,
                session_type=request.session_type,
                owner_user_id=user.id,
            )
        except CommitmentRequired as error:
            raise HTTPException(status_code=428, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error.args[0])) from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return SessionResponse.from_domain(session)

    @router.post("/{session_id}/cancel", response_model=SessionResponse)
    def cancel(session_id: str, user: User = Depends(current_user)) -> SessionResponse:
        service, _ = services()
        session = service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        require_session_access(user, session)
        # El docente no interrumpe el análisis en vivo que conduce otra cuenta.
        if session.owner_user_id not in (None, user.id) or (session.owner_user_id is None and user.role is not Role.STUDENT):
            raise HTTPException(status_code=403, detail="Solo quien conduce la sesión puede cancelarla")
        try:
            cancelled = service.cancel_session(session.id)
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return SessionResponse.from_domain(cancelled)

    @router.get("/{session_id}", response_model=SessionResponse)
    def get_by_id(session_id: str, user: User = Depends(current_user)) -> SessionResponse:
        service, _ = services()
        session = service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        require_session_access(user, session)
        return SessionResponse.from_domain(session)

    @router.get("", response_model=list[SessionResponse])
    def list_sessions(
        student_id: str | None = None,
        user: User = Depends(current_user),
    ) -> list[SessionResponse]:
        service, _ = services()
        if user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            raise HTTPException(status_code=403, detail="El administrador y el superadministrador no acceden a sesiones")
        actor_id = actor_student_id(user)
        if user.role is Role.STUDENT:
            if actor_id is None:
                raise HTTPException(status_code=403, detail="Tu cuenta de usuario no tiene perfil asociado")
            if student_id is not None and student_id != actor_id:
                raise HTTPException(status_code=403, detail="Solo puedes ver tus sesiones")
            found = {item.id: item for item in service.list_sessions_by_student(actor_id)}
        elif student_id is not None:
            if assignments is None or not assignments.is_assigned(user.id, student_id):
                raise HTTPException(status_code=403, detail="Este usuario no pertenece a tu grupo")
            found = {item.id: item for item in service.list_sessions_by_student(student_id)}
        else:
            # Sin filtro, el docente ve las sesiones de su grupo y las propias.
            assigned = assignments.list_by_psychologist(user.id) if assignments is not None else ()
            found = {item.id: item for assignment in assigned
                     for item in service.list_sessions_by_student(assignment.student_id)}
        if student_id is None:
            found.update({item.id: item for item in service.list_sessions_by_owner(user.id)})
        visible = [item for item in found.values()
                   if policy.can_access_session(user, item, actor_student_id=actor_id)]
        return [SessionResponse.from_domain(item) for item in sorted(visible, key=lambda item: (item.started_at, item.id))]

    return router
