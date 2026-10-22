from __future__ import annotations

from collections.abc import Callable

from emotv.domain.access_action import AccessAction
from emotv.domain.participant import Participant
from emotv.domain.role import CONDUCTOR_ROLES, Role
from emotv.domain.session import EmotionalSession
from emotv.domain.user import User


ROLE_ACTIONS: dict[Role, frozenset[AccessAction]] = {
    # Usuario: conduce sesiones con sus participantes y ve solo lo suyo.
    Role.STUDENT: frozenset({
        AccessAction.START_SESSION,
        AccessAction.CANCEL_SESSION,
        AccessAction.VIEW_SESSION,
        AccessAction.LIST_STUDENT_SESSIONS,
        AccessAction.MANAGE_CONSENT,
        AccessAction.REGISTER_PARTICIPANT,
    }),
    # Docente: ve los resultados de su grupo y conduce sesiones propias.
    Role.PSYCHOLOGIST: frozenset({
        AccessAction.START_SESSION,
        AccessAction.CANCEL_SESSION,
        AccessAction.VIEW_SESSION,
        AccessAction.LIST_STUDENT_SESSIONS,
        AccessAction.REGISTER_PARTICIPANT,
    }),
    # Administrador: cuentas de docentes y usuarios, grupos y auditoría.
    Role.ADMIN: frozenset({
        AccessAction.REGISTER_USER,
        AccessAction.MANAGE_USERS,
        AccessAction.MANAGE_STUDENTS,
        AccessAction.VIEW_AUDIT,
    }),
    # Superadministrador: soporte técnico y la cuenta de administrador.
    Role.SUPERADMIN: frozenset({
        AccessAction.MANAGE_USERS,
        AccessAction.MANAGE_ACTIVITIES,
        AccessAction.MANAGE_TECHNICAL,
        AccessAction.MANAGE_ADMIN_ACCOUNT,
        AccessAction.VIEW_AUDIT,
    }),
}

STUDENT_SCOPED_ACTIONS = frozenset({
    AccessAction.START_SESSION,
    AccessAction.CANCEL_SESSION,
    AccessAction.VIEW_SESSION,
    AccessAction.LIST_STUDENT_SESSIONS,
    AccessAction.MANAGE_CONSENT,
})


AssignmentCheck = Callable[[str, str], bool]
DocenteOf = Callable[[str], str | None]
ParticipantLookup = Callable[[str], Participant | None]


class AuthorizationService:
    """Evalúa permisos de rol, propiedad y grupo sin depender de la interfaz web.

    ``is_assigned(docente_user_id, student_id)`` responde si el usuario con ese
    perfil pertenece al grupo del docente. ``docente_of(user_id)`` devuelve el
    docente vigente de un usuario. Sin esas funciones el docente no accede a
    datos ajenos (se deniega por defecto). El administrador y el
    superadministrador nunca acceden a participantes, sesiones ni resultados.
    """

    def __init__(
        self,
        is_assigned: AssignmentCheck | None = None,
        docente_of: DocenteOf | None = None,
        participants: ParticipantLookup | None = None,
    ) -> None:
        self.is_assigned = is_assigned
        self.docente_of = docente_of
        self.participants = participants

    def can_access_participant(self, user: User, participant: Participant | None) -> bool:
        """Única regla de acceso a un participante y todo lo suyo (sesiones,
        capturas, cuestionarios y reportes): quien lo registró y el docente
        asignado a esa persona en este momento."""
        if participant is None or not isinstance(user, User) or not user.is_active:
            return False
        if user.role not in CONDUCTOR_ROLES:
            return False
        if participant.registered_by_user_id == user.id:
            return True
        return (
            user.role is Role.PSYCHOLOGIST
            and self.docente_of is not None
            and self.docente_of(participant.registered_by_user_id) == user.id
        )

    def can_access_session(
        self,
        user: User,
        session: EmotionalSession,
        *,
        actor_student_id: str | None = None,
    ) -> bool:
        """Una sesión con participante sigue la regla del participante; una
        propia, a quien la conduce, su perfil y su docente."""
        if not isinstance(user, User) or not user.is_active or user.role not in CONDUCTOR_ROLES:
            return False
        if session.participant_id is not None:
            participant = self.participants(session.participant_id) if self.participants else None
            return self.can_access_participant(user, participant)
        if session.owner_user_id is not None and session.owner_user_id == user.id:
            return True
        if session.student_id is None:
            return False
        if user.role is Role.STUDENT:
            return actor_student_id is not None and actor_student_id.strip() == session.student_id
        return self.is_assigned is not None and self.is_assigned(user.id, session.student_id)

    def is_allowed(
        self,
        user: User,
        action: AccessAction | str,
        *,
        resource_student_id: str | None = None,
        actor_student_id: str | None = None,
    ) -> bool:
        if not isinstance(user, User) or not user.is_active:
            return False
        try:
            normalized_action = AccessAction(action)
        except ValueError:
            return False
        if normalized_action not in ROLE_ACTIONS[user.role]:
            return False

        if user.role is Role.STUDENT and normalized_action in STUDENT_SCOPED_ACTIONS:
            return (
                actor_student_id is not None
                and resource_student_id is not None
                and actor_student_id.strip() == resource_student_id.strip()
                and bool(actor_student_id.strip())
            )
        if user.role is Role.PSYCHOLOGIST and normalized_action in STUDENT_SCOPED_ACTIONS:
            if resource_student_id is None:
                # Sesión propia del docente: sin perfil de usuario asociado.
                return normalized_action is AccessAction.START_SESSION
            return (
                self.is_assigned is not None
                and bool(resource_student_id.strip())
                and self.is_assigned(user.id, resource_student_id.strip())
            )
        return True

    def require(
        self,
        user: User,
        action: AccessAction | str,
        *,
        resource_student_id: str | None = None,
        actor_student_id: str | None = None,
    ) -> None:
        if not self.is_allowed(
            user,
            action,
            resource_student_id=resource_student_id,
            actor_student_id=actor_student_id,
        ):
            action_name = action.value if isinstance(action, AccessAction) else str(action)
            raise PermissionError(f"Acceso denegado para la acción: {action_name}")
