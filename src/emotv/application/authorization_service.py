from __future__ import annotations

from collections.abc import Callable

from emotv.domain.access_action import AccessAction
from emotv.domain.role import CONDUCTOR_ROLES, Role
from emotv.domain.session import EmotionalSession
from emotv.domain.user import User


ROLE_ACTIONS: dict[Role, frozenset[AccessAction]] = {
    # Usuario: conduce sesiones (propias o con otras personas) y ve solo las suyas.
    Role.STUDENT: frozenset({
        AccessAction.START_SESSION,
        AccessAction.CANCEL_SESSION,
        AccessAction.VIEW_SESSION,
        AccessAction.LIST_STUDENT_SESSIONS,
        AccessAction.MANAGE_CONSENT,
    }),
    # Docente: ve los resultados de su grupo y conduce sesiones propias.
    Role.PSYCHOLOGIST: frozenset({
        AccessAction.START_SESSION,
        AccessAction.CANCEL_SESSION,
        AccessAction.VIEW_SESSION,
        AccessAction.LIST_STUDENT_SESSIONS,
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


class AuthorizationService:
    """Evalúa permisos de rol, propiedad y grupo sin depender de la interfaz web.

    ``is_assigned(docente_user_id, student_id)`` responde si el usuario con ese
    perfil pertenece al grupo del docente. ``docente_of(user_id)`` devuelve el
    docente vigente de un usuario. Sin esas funciones el docente no accede a
    datos ajenos (se deniega por defecto). El administrador y el
    superadministrador nunca acceden a sesiones ni resultados.
    """

    def __init__(
        self,
        is_assigned: AssignmentCheck | None = None,
        docente_of: DocenteOf | None = None,
    ) -> None:
        self.is_assigned = is_assigned
        self.docente_of = docente_of

    def can_access_session(
        self,
        user: User,
        session: EmotionalSession | None,
        *,
        actor_student_id: str | None = None,
    ) -> bool:
        """Única regla de acceso a una sesión y todo lo suyo (capturas,
        cuestionarios, marcadores y reporte): quien la condujo y el docente
        asignado a esa cuenta en este momento. Nunca la administración."""
        if session is None or not isinstance(user, User) or not user.is_active or user.role not in CONDUCTOR_ROLES:
            return False
        if session.owner_user_id is not None:
            if session.owner_user_id == user.id:
                return True
            return (user.role is Role.PSYCHOLOGIST and self.docente_of is not None
                    and self.docente_of(session.owner_user_id) == user.id)
        # Sesiones anteriores a owner_user_id: el perfil del usuario y su docente.
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
