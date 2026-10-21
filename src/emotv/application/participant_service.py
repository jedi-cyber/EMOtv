"""Participantes: registro, acceso, vencimiento y eliminación verificable.

Todo acceso pasa por AuthorizationService.can_access_participant. Los
participantes no tienen cuenta: se identifican con un código aleatorio.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import logging
import secrets
from uuid import uuid4

from emotv.application.audit_service import DAYS_PER_MONTH, AuditService
from emotv.application.authorization_service import AuthorizationService
from emotv.application.commitment_service import CHILD_NOTICE, CommitmentService
from emotv.application.ports.privacy_repositories import (
    DeletionCertificate,
    ErasureVerificationError,
    ParticipantRepository,
)
from emotv.domain.access_action import AccessAction
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.participant import Participant, ParticipantKind
from emotv.domain.role import Role
from emotv.domain.user import User

logger = logging.getLogger(__name__)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I/L
RESOURCE = "participant"
CERTIFICATE = "deletion_certificate"


def random_code() -> str:
    return "P-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


class ChildNoticeRequired(PermissionError):
    """Falta aceptar el aviso reforzado antes del primer participante niño."""


class ParticipantNotFound(LookupError):
    pass


class ParticipantService:
    def __init__(
        self,
        repository: ParticipantRepository,
        authorization: AuthorizationService,
        commitments: CommitmentService,
        audit: AuditService,
        group_user_ids: Callable[[str], Iterable[str]],
        retention_months: int = 12,
        notice_days: int = 30,
        clock: Callable[[], datetime] | None = None,
        code_factory: Callable[[], str] = random_code,
    ) -> None:
        self.repository = repository
        self.authorization = authorization
        self.commitments = commitments
        self.audit = audit
        self.group_user_ids = group_user_ids
        self.retention = timedelta(days=retention_months * DAYS_PER_MONTH)
        self.notice = timedelta(days=notice_days)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.code_factory = code_factory

    def expires_at(self, participant: Participant) -> datetime:
        return participant.created_at + self.retention

    def register(self, user: User, kind: ParticipantKind | str, notes: str | None = None,
                 child_notice_version: str | None = None) -> Participant:
        if not self.authorization.is_allowed(user, AccessAction.REGISTER_PARTICIPANT):
            raise PermissionError("Solo usuarios y docentes registran participantes")
        self.commitments.require(user)
        kind = ParticipantKind(kind)
        if kind is ParticipantKind.CHILD and not self.commitments.has_accepted(user, CHILD_NOTICE):
            if child_notice_version is None:
                raise ChildNoticeRequired("Lee y acepta el aviso sobre datos de menores antes de registrar a un niño")
            self.commitments.accept(user, child_notice_version, CHILD_NOTICE)
        code = self.code_factory()
        while self.repository.code_exists(code):
            code = self.code_factory()
        participant = self.repository.save(Participant(
            id=str(uuid4()), code=code, kind=kind, registered_by_user_id=user.id,
            created_at=self.clock(), notes=notes,
        ))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, participant.id)
        return participant

    def get(self, user: User, participant_id: str) -> Participant:
        participant = self.repository.get_by_id(participant_id)
        if participant is None:
            raise ParticipantNotFound(participant_id)
        if not self.authorization.can_access_participant(user, participant):
            self.audit.record(user, AuditAction.VIEW, RESOURCE, participant.id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a este participante")
        self.audit.record(user, AuditAction.VIEW, RESOURCE, participant.id)
        return participant

    def _registrants(self, user: User) -> tuple[str, ...]:
        if user.role is Role.STUDENT:
            return (user.id,)
        if user.role is Role.PSYCHOLOGIST:
            return (user.id, *self.group_user_ids(user.id))
        raise PermissionError("El administrador y el superadministrador no acceden a participantes")

    def list_for(self, user: User) -> tuple[Participant, ...]:
        items = self.repository.list_by_registrants(self._registrants(user))
        # Defensa adicional: la misma regla central filtra cada elemento.
        visible = tuple(item for item in items if self.authorization.can_access_participant(user, item))
        self.audit.record(user, AuditAction.VIEW, "participant_list", str(len(visible)))
        return visible

    def expiring(self, user: User) -> tuple[Participant, ...]:
        """Participantes que vencen en los próximos días de aviso (solo docentes)."""
        if user.role is not Role.PSYCHOLOGIST:
            raise PermissionError("La lista de vencimientos es para docentes")
        now = self.clock()
        items = self.repository.list_by_registrants(self._registrants(user))
        return tuple(item for item in items
                     if now < self.expires_at(item) <= now + self.notice
                     and self.authorization.can_access_participant(user, item))

    def request_deletion(self, user: User, participant_id: str) -> Participant:
        participant = self.get(user, participant_id)
        if participant.registered_by_user_id != user.id:
            raise PermissionError("Solo quien registró al participante puede solicitar su eliminación")
        if participant.deletion_requested_at is not None:
            return participant
        updated = self.repository.save(replace(participant, deletion_requested_at=self.clock(),
                                               deletion_requested_by_user_id=user.id))
        self.audit.record(user, AuditAction.DELETION_REQUEST, RESOURCE, participant.id)
        return updated

    def delete(self, user: User, participant_id: str) -> DeletionCertificate:
        """El docente ejecuta la eliminación (a pedido o por iniciativa propia)."""
        if user.role is not Role.PSYCHOLOGIST:
            raise PermissionError("La eliminación la ejecuta el docente")
        participant = self.get(user, participant_id)
        try:
            certificate = self.repository.erase_with_certificate(
                participant.id, str(uuid4()), self.clock(), user.id, participant.deletion_requested_by_user_id)
        except ErasureVerificationError:
            self.audit.record(user, AuditAction.DELETE, RESOURCE, participant.id, AuditResult.FAILURE)
            raise
        self.audit.record(user, AuditAction.DELETE, RESOURCE, participant.id)
        return certificate

    def certificate(self, user: User, certificate_id: str, *, printing: bool = False) -> DeletionCertificate:
        certificate = self.repository.get_certificate(certificate_id)
        if certificate is None:
            raise ParticipantNotFound(certificate_id)
        if user.id not in (certificate.executed_by_user_id, certificate.requested_by_user_id):
            self.audit.record(user, AuditAction.VIEW, CERTIFICATE, certificate_id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a esta acta")
        self.audit.record(user, AuditAction.PRINT if printing else AuditAction.VIEW, CERTIFICATE, certificate_id)
        return certificate

    def certificates_for(self, user: User) -> tuple[DeletionCertificate, ...]:
        if user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            raise PermissionError("El administrador y el superadministrador no acceden a participantes")
        return self.repository.list_certificates_by((user.id,))

    def purge_expired(self) -> int:
        """Elimina los participantes vencidos con todos sus registros y audita
        solo la cantidad. Un participante que falle la verificación se conserva."""
        cutoff = self.clock() - self.retention
        removed = 0
        for participant in self.repository.list_created_before(cutoff):
            try:
                self.repository.erase(participant.id)
                removed += 1
            except ErasureVerificationError:
                logger.error("La retención no pudo verificar la eliminación de un participante; se revirtió")
        if removed:
            self.audit.record(None, AuditAction.RETENTION_PURGE, RESOURCE, str(removed))
            logger.info("Retención de participantes: %s eliminados", removed)
        return removed
