from __future__ import annotations

from collections.abc import Callable

from emotv.domain.access_action import AccessAction
from emotv.domain.role import Role
from emotv.domain.user import User


ROLE_ACTIONS: dict[Role, frozenset[AccessAction]] = {
    Role.STUDENT: frozenset({
        AccessAction.START_SESSION,
        AccessAction.CANCEL_SESSION,
        AccessAction.VIEW_SESSION,
        AccessAction.LIST_STUDENT_SESSIONS,
        AccessAction.MANAGE_CONSENT,
    }),
    # Sin START_SESSION ni CANCEL_SESSION: el análisis lo hace el estudiante
    # con su cámara; una sesión iniciada por el psicólogo quedaría huérfana y
    # cancelar solo serviría para interrumpir el análisis en vivo de otro.
    Role.PSYCHOLOGIST: frozenset({
        AccessAction.VIEW_SESSION,
        AccessAction.LIST_STUDENT_SESSIONS,
    }),
    Role.ADMIN: frozenset(AccessAction),
}

STUDENT_SCOPED_ACTIONS = frozenset({
    AccessAction.START_SESSION,
    AccessAction.CANCEL_SESSION,
    AccessAction.VIEW_SESSION,
    AccessAction.LIST_STUDENT_SESSIONS,
    AccessAction.MANAGE_CONSENT,
})


AssignmentCheck = Callable[[str, str], bool]


class AuthorizationService:
    """Evalúa permisos de rol, propiedad y asignación sin depender de la interfaz web.

    ``is_assigned(psicólogo_user_id, student_id)`` responde si el psicólogo
    tiene asignado al estudiante. Sin esa función, el psicólogo no accede a
    ningún estudiante (se deniega por defecto).
    """

    def __init__(self, is_assigned: AssignmentCheck | None = None) -> None:
        self.is_assigned = is_assigned

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
            return (
                self.is_assigned is not None
                and resource_student_id is not None
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
