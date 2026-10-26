"""Sesiones: inicio, consulta, cancelación y eliminación con acta.

Una sesión aplica un protocolo (una receta guardada) o ninguno. No se registra a
la persona evaluada: la sesión lleva un código aleatorio que quien conduce anota
en el formato firmado. Se inicia con una sola confirmación de la autorización,
según el público: el del protocolo o, sin protocolo, el que elige quien conduce.
Todo acceso pasa por can_access_session.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from emotv.application import ActivityCatalog, AuthenticationService, AuthorizationService, SessionService
from emotv.application.audit_service import AuditService
from emotv.application.ports import StudentRepository, UserRepository
from emotv.application.ports.assignment_repository import AssignmentRepository
from emotv.application.ports.privacy_repositories import DeletionCertificate, ErasureVerificationError
from emotv.application.session_privacy_service import DeletionConflict, SessionNotFound, SessionPrivacyService
from emotv.domain import AccessAction, EmotionalSession, Role, SessionType, User
from emotv.domain.audit import AuditAction
from emotv.interfaces.web.auth_router import create_current_user_dependency
from emotv.application.commitment_service import CHILD_NOTICE, CommitmentRequired, CommitmentService
from emotv.application.protocol_service import ProtocolNotFound, ProtocolService, ProtocolUnavailable
from emotv.application.questionnaire_service import QuestionnaireNotFound, QuestionnaireService


SessionTypeValue = Literal["propia", "adulto", "infantil"]
SESSION_RESOURCE = "session"
# Qué falta aceptar en un 428: el compromiso o el aviso sobre datos de menores.
REQUIRED_HEADER = "X-EMOtv-Required"
CONFIRMATIONS = {
    SessionType.OWN.value: "Es una sesión mía o cuento con la autorización firmada de la persona adulta",
    SessionType.ADULT.value: "Es una sesión mía o cuento con la autorización firmada de la persona adulta",
    SessionType.CHILD.value: "Su tutor autorizó por escrito, está presente y el niño aceptó participar",
}


class ChildNoticeRequired(PermissionError):
    """Falta aceptar el aviso sobre datos de menores antes de la primera sesión con un niño."""


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str | None = None
    activity_id: str | None = None
    # Versión del protocolo que se aplica. Con protocolo, su público decide.
    protocol_id: str | None = None
    # Sin protocolo, ¿con quién es la sesión? Conmigo, un adulto o un niño o niña.
    session_type: SessionTypeValue | None = None
    # La única confirmación de la sesión, según el público (CONFIRMATIONS).
    authorization_confirmed: bool = False
    # Versión del aviso sobre datos de menores, la primera vez que se hace una sesión con un niño.
    child_notice_version: str | None = Field(default=None, max_length=32)


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
    protocol_id: str | None = None
    pre_questionnaire_id: str | None = None
    post_questionnaire_id: str | None = None
    # Código que se anota en el formato firmado.
    code: str | None = None
    authorization_confirmed_at: datetime | None = None
    deletion_requested_at: datetime | None = None

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
                   owner_user_id=session.owner_user_id,
                   protocol_id=session.protocol_id,
                   pre_questionnaire_id=session.pre_questionnaire_id,
                   post_questionnaire_id=session.post_questionnaire_id,
                   code=session.code,
                   authorization_confirmed_at=session.authorization_confirmed_at,
                   deletion_requested_at=session.deletion_requested_at)


class DeletionCertificateResponse(BaseModel):
    id: str
    session_code: str
    deleted_at: datetime
    counts: dict[str, int]
    verified: bool

    @classmethod
    def from_domain(cls, item: DeletionCertificate) -> "DeletionCertificateResponse":
        return cls(id=item.id, session_code=item.session_code, deleted_at=item.deleted_at, counts=item.counts,
                   verified=item.verified)


def create_session_starter(
    sessions: SessionService | None,
    students: StudentRepository | None,
    policy: AuthorizationService,
    activities: ActivityCatalog | None = None,
    commitments: CommitmentService | None = None,
    protocols: ProtocolService | None = None,
    questionnaires: QuestionnaireService | None = None,
    audit: AuditService | None = None,
) -> Callable[[User, CreateSessionRequest], EmotionalSession]:
    """Inicia una sesión con las mismas reglas para la web y el aplicativo móvil:
    compromiso, una sola confirmación según el público, aviso sobre menores la
    primera vez, protocolo utilizable y cuestionarios vigentes. Lanza
    HTTPException con el código del contrato."""

    def services() -> tuple[SessionService, StudentRepository]:
        if sessions is None or students is None:
            raise HTTPException(status_code=503, detail="Sesiones no configuradas")
        return sessions, students

    def start(user: User, request: CreateSessionRequest) -> EmotionalSession:
        service, student_repository = services()
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
            questionnaire_ids: tuple[str | None, str | None] = (None, None)
            if request.protocol_id is not None:
                if protocols is None:
                    raise HTTPException(status_code=503, detail="Los protocolos no están configurados")
                protocol = protocols.require_usable(user, request.protocol_id)
                # Con protocolo no se pregunta nada más: el público es el del protocolo.
                audience = SessionType.CHILD if protocol.for_children else SessionType.ADULT
                chosen = SessionType(request.session_type) if request.session_type else audience
                if (chosen is SessionType.CHILD) != (audience is SessionType.CHILD):
                    raise HTTPException(status_code=422, detail="Con protocolo, el público es el del protocolo")
                # Un protocolo para adultos también sirve para una sesión propia.
                audience = chosen
                questionnaire_ids = (protocol.pre_questionnaire_id, protocol.post_questionnaire_id)
            elif request.session_type is None:
                raise HTTPException(status_code=422, detail="Elige con quién es la sesión o un protocolo")
            else:
                audience = SessionType(request.session_type)
            if not request.authorization_confirmed:
                raise HTTPException(status_code=422, detail=f"Confirma: {CONFIRMATIONS[audience.value]}")
            if audience is SessionType.CHILD and commitments is not None                     and not commitments.has_accepted(user, CHILD_NOTICE):
                if request.child_notice_version is None:
                    raise ChildNoticeRequired("Lee y acepta el aviso sobre datos de menores antes de la primera "
                                              "sesión con un niño o una niña")
                commitments.accept(user, request.child_notice_version, CHILD_NOTICE)
            if any(questionnaire_ids):
                if questionnaires is None or questionnaires.responses is None:
                    raise HTTPException(status_code=503, detail="Los cuestionarios no están disponibles: falta la "
                                                                "clave de cifrado de datos sensibles")
                # Se aplica la versión vigente; la sesión guarda esa versión exacta.
                questionnaire_ids = tuple(questionnaires.current_for(user, item).id if item else None
                                          for item in questionnaire_ids)
            session = service.start_session(
                student_id=resource_id,
                activity_id=request.activity_id,
                session_type=audience,
                owner_user_id=user.id,
                protocol_id=request.protocol_id,
                pre_questionnaire_id=questionnaire_ids[0],
                post_questionnaire_id=questionnaire_ids[1],
                authorization_confirmed=True,
            )
            if audit is not None:
                audit.record(user, AuditAction.CREATE, SESSION_RESOURCE, session.id)
        except CommitmentRequired as error:
            raise HTTPException(status_code=428, detail=str(error)) from error
        except ChildNoticeRequired as error:
            raise HTTPException(status_code=428, detail=str(error),
                                headers={REQUIRED_HEADER: "child_notice"}) from error
        except (ProtocolNotFound, QuestionnaireNotFound) as error:
            raise HTTPException(status_code=404, detail="Protocolo o cuestionario no encontrado") from error
        except ProtocolUnavailable as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error.args[0])) from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return session

    return start


def create_session_router(
    sessions: SessionService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    students: StudentRepository | None,
    authorization: AuthorizationService | None = None,
    activities: ActivityCatalog | None = None,
    assignments: AssignmentRepository | None = None,
    commitments: CommitmentService | None = None,
    protocols: ProtocolService | None = None,
    questionnaires: QuestionnaireService | None = None,
    privacy: SessionPrivacyService | None = None,
    audit: AuditService | None = None,
) -> APIRouter:
    router = APIRouter(tags=["sessions"])
    policy = authorization or AuthorizationService()
    current_user = create_current_user_dependency(authentication, users)
    starter = create_session_starter(sessions, students, policy, activities, commitments, protocols,
                                     questionnaires, audit)

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

    @router.post("/sessions", response_model=SessionResponse, status_code=201)
    def start(request: CreateSessionRequest, user: User = Depends(current_user)) -> SessionResponse:
        return SessionResponse.from_domain(starter(user, request))

    @router.post("/sessions/{session_id}/cancel", response_model=SessionResponse)
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

    @router.get("/sessions/{session_id}", response_model=SessionResponse)
    def get_by_id(session_id: str, user: User = Depends(current_user)) -> SessionResponse:
        service, _ = services()
        session = service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        require_session_access(user, session)
        return SessionResponse.from_domain(session)

    @router.get("/sessions", response_model=list[SessionResponse])
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

    # --- Eliminación por sesión, con acta ---------------------------------------------

    def privacy_service() -> SessionPrivacyService:
        if privacy is None:
            raise HTTPException(status_code=503, detail="La eliminación de sesiones no está configurada")
        return privacy

    def guarded(operation):
        try:
            return operation()
        except SessionNotFound as error:
            raise HTTPException(status_code=404, detail="Sesión o acta no encontrada") from error
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except DeletionConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ErasureVerificationError as error:
            raise HTTPException(status_code=500, detail="La verificación de la eliminación falló; no se borró nada") \
                from error

    @router.post("/sessions/{session_id}/deletion-request", response_model=SessionResponse)
    def request_deletion(session_id: str, user: User = Depends(current_user)) -> SessionResponse:
        """Quien condujo la sesión pide eliminarla; la ejecuta su docente."""
        return SessionResponse.from_domain(guarded(
            lambda: privacy_service().request_deletion(user, session_id, actor_student_id(user))))

    @router.post("/sessions/{session_id}/delete", response_model=DeletionCertificateResponse)
    def delete_session(session_id: str, user: User = Depends(current_user)) -> DeletionCertificateResponse:
        """El docente elimina la sesión con todos sus registros y recibe el acta."""
        return DeletionCertificateResponse.from_domain(guarded(
            lambda: privacy_service().delete(user, session_id, actor_student_id(user))))

    @router.get("/session-deletions", response_model=list[DeletionCertificateResponse])
    def list_certificates(user: User = Depends(current_user)) -> list[DeletionCertificateResponse]:
        return [DeletionCertificateResponse.from_domain(item)
                for item in guarded(lambda: privacy_service().certificates_for(user))]

    @router.get("/session-deletions/{certificate_id}", response_model=DeletionCertificateResponse)
    def get_certificate(certificate_id: str, user: User = Depends(current_user)) -> DeletionCertificateResponse:
        return DeletionCertificateResponse.from_domain(guarded(
            lambda: privacy_service().certificate(user, certificate_id)))

    @router.post("/session-deletions/{certificate_id}/print", response_model=DeletionCertificateResponse)
    def print_certificate(certificate_id: str, user: User = Depends(current_user)) -> DeletionCertificateResponse:
        """Registra la impresión del acta en la auditoría y devuelve su contenido."""
        return DeletionCertificateResponse.from_domain(guarded(
            lambda: privacy_service().certificate(user, certificate_id, printing=True)))

    return router
