from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AuditAction(str, Enum):
    """Acciones auditables. La auditoría nunca guarda contenido ni imágenes."""

    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    PRINT = "print"
    APPROVE = "approve"
    DELETE = "delete"
    DELETION_REQUEST = "deletion_request"
    RETENTION_PURGE = "retention_purge"
    AUTHORIZATION_CHANGE = "authorization_change"
    PASSWORD_RESET = "password_reset"
    GROUP_CHANGE = "group_change"
    ACCOUNT_CREATE = "account_create"
    ACCOUNT_DEACTIVATE = "account_deactivate"
    ACCOUNT_REACTIVATE = "account_reactivate"
    COMMITMENT_ACCEPT = "commitment_accept"
    CHILD_NOTICE_ACCEPT = "child_notice_accept"


class AuditResult(str, Enum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Quién hizo qué sobre qué recurso y con qué resultado.

    resource_id es un identificador interno o, para la retención, una cantidad;
    nunca notas, respuestas, correos ni imágenes. actor_user_id es nulo en las
    tareas automáticas del sistema.
    """

    id: str
    occurred_at: datetime
    actor_user_id: str | None
    actor_role: str | None
    action: AuditAction | str
    resource_type: str
    resource_id: str | None
    result: AuditResult | str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at debe incluir zona horaria")
        object.__setattr__(self, "action", AuditAction(self.action))
        object.__setattr__(self, "result", AuditResult(self.result))
        if not self.resource_type.strip():
            raise ValueError("resource_type no puede estar vacío")
