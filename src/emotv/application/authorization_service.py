from __future__ import annotations

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
    Role.PSYCHOLOGIST: frozenset({
        AccessAction.START_SESSION,
        AccessAction.CANCEL_SESSION,
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


class AuthorizationService:
    """Evalúa permisos de rol y propiedad sin depender de la interfaz web."""

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
