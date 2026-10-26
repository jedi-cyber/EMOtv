"""Retención y eliminación por sesión, con acta.

No hay registro de personas evaluadas: cada sesión lleva solo un código
aleatorio. Quien condujo la sesión solicita su eliminación y su docente la
ejecuta (un docente elimina directamente las suyas y las de su grupo). El acta
guarda el código de la sesión, la fecha, los registros borrados por tipo y la
verificación, sin datos personales. La retención borra las sesiones iniciadas
hace más de SESSION_RETENTION_MONTHS.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4

from emotv.application.audit_service import DAYS_PER_MONTH, AuditService
from emotv.application.authorization_service import AuthorizationService
from emotv.application.ports.privacy_repositories import (
    DeletionCertificate,
    ErasureVerificationError,
    SessionErasureRepository,
)
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.role import Role
from emotv.domain.session import EmotionalSession
from emotv.domain.user import User

logger = logging.getLogger(__name__)
RESOURCE = "session"
CERTIFICATE = "deletion_certificate"


class SessionNotFound(LookupError):
    pass


class DeletionConflict(Exception):
    """La sesión todavía está en curso: se elimina cuando termina."""


class SessionPrivacyService:
    def __init__(
        self,
        sessions,                                   # SessionService
        erasure: SessionErasureRepository,
        authorization: AuthorizationService,
        audit: AuditService,
        docente_of: Callable[[str], str | None],
        retention_months: int = 12,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.sessions = sessions
        self.erasure = erasure
        self.authorization = authorization
        self.audit = audit
        self.docente_of = docente_of
        self.retention = timedelta(days=retention_months * DAYS_PER_MONTH)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def expires_at(self, session: EmotionalSession) -> datetime:
        return session.started_at + self.retention

    def _accessible(self, user: User, session_id: str, actor_student_id: str | None) -> EmotionalSession:
        session = self.sessions.get_session(session_id)
        if session is None:
            raise SessionNotFound(session_id)
        if not self.authorization.can_access_session(user, session, actor_student_id=actor_student_id):
            self.audit.record(user, AuditAction.VIEW, RESOURCE, session.id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a esta sesión")
        return session

    def can_execute(self, user: User, session: EmotionalSession) -> bool:
        """El docente ejecuta: las sesiones que condujo y las de su grupo."""
        if user.role is not Role.PSYCHOLOGIST or not user.is_active or session.owner_user_id is None:
            return False
        return session.owner_user_id == user.id or self.docente_of(session.owner_user_id) == user.id

    def request_deletion(self, user: User, session_id: str, actor_student_id: str | None = None) -> EmotionalSession:
        session = self._accessible(user, session_id, actor_student_id)
        if session.owner_user_id != user.id:
            raise PermissionError("Solo quien condujo la sesión solicita su eliminación")
        if session.deletion_requested_at is not None:
            return session
        updated = self.sessions.request_deletion(session.id, user.id)
        self.audit.record(user, AuditAction.DELETION_REQUEST, RESOURCE, session.id)
        return updated

    def delete(self, user: User, session_id: str, actor_student_id: str | None = None) -> DeletionCertificate:
        """El docente ejecuta la eliminación (a pedido o por iniciativa propia)."""
        session = self._accessible(user, session_id, actor_student_id)
        if not self.can_execute(user, session):
            raise PermissionError("La eliminación la ejecuta el docente")
        if not session.is_terminal:
            raise DeletionConflict("La sesión sigue en curso: termínala antes de eliminarla")
        try:
            certificate = self.erasure.erase_with_certificate(
                session.id, str(uuid4()), self.clock(), user.id, session.deletion_requested_by_user_id)
        except ErasureVerificationError:
            self.audit.record(user, AuditAction.DELETE, RESOURCE, session.id, AuditResult.FAILURE)
            raise
        self.audit.record(user, AuditAction.DELETE, RESOURCE, session.id)
        return certificate

    def certificate(self, user: User, certificate_id: str, *, printing: bool = False) -> DeletionCertificate:
        certificate = self.erasure.get_certificate(certificate_id)
        if certificate is None:
            raise SessionNotFound(certificate_id)
        if not user.is_active or user.id not in (certificate.executed_by_user_id, certificate.requested_by_user_id):
            self.audit.record(user, AuditAction.VIEW, CERTIFICATE, certificate_id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a esta acta")
        self.audit.record(user, AuditAction.PRINT if printing else AuditAction.VIEW, CERTIFICATE, certificate_id)
        return certificate

    def certificates_for(self, user: User) -> tuple[DeletionCertificate, ...]:
        if user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            raise PermissionError("El administrador y el superadministrador no acceden a sesiones")
        return self.erasure.list_certificates_by((user.id,))

    def purge_expired(self) -> int:
        """Elimina las sesiones vencidas con todos sus registros y audita solo
        la cantidad. Una sesión que falle la verificación se conserva."""
        cutoff = self.clock() - self.retention
        removed = 0
        for session in self.sessions.list_started_before(cutoff):
            try:
                self.erasure.erase(session.id)
                removed += 1
            except ErasureVerificationError:
                logger.error("La retención no pudo verificar la eliminación de una sesión; se revirtió")
        if removed:
            self.audit.record(None, AuditAction.RETENTION_PURGE, RESOURCE, str(removed))
            logger.info("Retención de sesiones: %s eliminadas", removed)
        return removed
