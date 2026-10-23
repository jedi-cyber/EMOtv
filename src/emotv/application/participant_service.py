"""Participantes: registro, autorizaciones firmadas, acceso, vencimiento y
eliminación verificable.

Todo acceso pasa por AuthorizationService.can_access_participant. Los
participantes no tienen cuenta: se identifican con un código aleatorio y su
edad en años. Las autorizaciones se registran a partir del formato firmado en
papel; sin participación (a), cámara (b) y, en niños, asentimiento, no se
inicia ninguna sesión.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import logging
import secrets
from uuid import uuid4

from emotv.application.audit_service import DAYS_PER_MONTH, AuditService
from emotv.application.authorization_service import AuthorizationService
from emotv.application.commitment_service import CHILD_NOTICE, CommitmentService
from emotv.application.ports.practice_repositories import AuthorizationRepository
from emotv.application.ports.privacy_repositories import (
    DeletionCertificate,
    ErasureVerificationError,
    ParticipantRepository,
)
from emotv.domain.access_action import AccessAction
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.participant import Participant, ParticipantKind, kind_for_age
from emotv.domain.participant_authorization import Grantor, ParticipantAuthorization, RevokedScope
from emotv.domain.role import Role
from emotv.domain.user import User

logger = logging.getLogger(__name__)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I/L
RESOURCE = "participant"
CERTIFICATE = "deletion_certificate"
AUTHORIZATION = "participant_authorization"
SESSION = "participant_session"


def random_code() -> str:
    return "P-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


class ChildNoticeRequired(PermissionError):
    """Falta aceptar el aviso reforzado antes del primer participante niño."""


class ParticipantNotFound(LookupError):
    pass


class SessionNotAllowed(Exception):
    """El participante no puede iniciar una sesión: faltan autorizaciones o se retiraron."""


class AuthorizationStatus:
    READY = "ready"            # (a), (b) y, en niños, asentimiento
    MISSING = "missing"        # sin formato registrado o incompleto
    REVOKED = "revoked"        # se retiró una autorización
    NO_AGE = "no_age"          # registrado antes de pedir la edad


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
        authorizations: AuthorizationRepository | None = None,
    ) -> None:
        self.repository = repository
        self.authorizations = authorizations
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
                 child_notice_version: str | None = None, age_years: int | None = None) -> Participant:
        """Registra a un participante con un código aleatorio no editable y su
        edad en años. Sin nombre, DNI, foto ni datos del tutor."""
        if not self.authorization.is_allowed(user, AccessAction.REGISTER_PARTICIPANT):
            raise PermissionError("Solo usuarios y docentes registran participantes")
        self.commitments.require(user)
        kind = ParticipantKind(kind)
        if age_years is None:
            raise ValueError("Indica la edad del participante en años")
        if kind_for_age(age_years) is not kind:
            raise ValueError("Un participante adulto tiene 18 años o más; un niño o niña, menos de 18")
        if kind is ParticipantKind.CHILD and not self.commitments.has_accepted(user, CHILD_NOTICE):
            if child_notice_version is None:
                raise ChildNoticeRequired("Lee y acepta el aviso sobre datos de menores antes de registrar a un niño")
            self.commitments.accept(user, child_notice_version, CHILD_NOTICE)
        code = self.code_factory()
        while self.repository.code_exists(code):
            code = self.code_factory()
        participant = self.repository.save(Participant(
            id=str(uuid4()), code=code, kind=kind, registered_by_user_id=user.id,
            created_at=self.clock(), notes=notes, age_years=age_years,
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

    # --- Autorizaciones firmadas en papel -----------------------------------

    def _authorization_store(self) -> AuthorizationRepository:
        if self.authorizations is None:
            raise RuntimeError("Las autorizaciones no están configuradas")
        return self.authorizations

    def status(self, participant: Participant,
               authorizations: tuple[ParticipantAuthorization, ...] | None = None) -> str:
        if participant.authorization_revoked_at is not None:
            return AuthorizationStatus.REVOKED
        if participant.age_years is None:
            return AuthorizationStatus.NO_AGE
        items = self._authorization_store().list_for(participant.id) if authorizations is None else authorizations
        latest = items[0] if items else None
        if latest is not None and latest.allows_sessions(participant.kind is ParticipantKind.CHILD):
            return AuthorizationStatus.READY
        return AuthorizationStatus.MISSING

    def list_authorizations(self, user: User, participant_id: str) -> tuple[ParticipantAuthorization, ...]:
        participant = self.get(user, participant_id)
        items = self._authorization_store().list_for(participant.id)
        self.audit.record(user, AuditAction.VIEW, AUTHORIZATION, participant.id)
        return items

    def record_authorization(self, user: User, participant_id: str, *, form_version: str, signed_on: date,
                             participation: bool, camera: bool,
                             child_assent: bool | None = None) -> ParticipantAuthorization:
        """Registra el formato firmado: lo otorga el propio participante adulto
        o, si es un niño, su padre, madre o tutor, más el asentimiento del niño."""
        participant = self.get(user, participant_id)
        if participant.authorization_revoked_at is not None:
            raise SessionNotAllowed("Se retiró una autorización de este participante: no se registran nuevas. "
                                    "Su docente decide su eliminación.")
        is_child = participant.kind is ParticipantKind.CHILD
        if is_child and child_assent is None:
            raise ValueError("Con un niño o niña, indica si dio su asentimiento")
        if not is_child and child_assent is not None:
            raise ValueError("El asentimiento solo se registra con niños")
        item = self._authorization_store().add(ParticipantAuthorization(
            id=str(uuid4()), participant_id=participant.id, form_version=form_version, signed_on=signed_on,
            grantor=Grantor.GUARDIAN if is_child else Grantor.PARTICIPANT,
            participation=participation, camera=camera, child_assent=child_assent,
            recorded_by_user_id=user.id, recorded_at=self.clock()))
        self.audit.record(user, AuditAction.CREATE, AUTHORIZATION, item.id)
        return item

    def revoke_authorization(self, user: User, participant_id: str, authorization_id: str, *,
                             party: Grantor | str, scope: RevokedScope | str) -> ParticipantAuthorization:
        """Registra que el participante o su tutor retiró una autorización. Las
        sesiones nuevas quedan bloqueadas y el participante queda marcado para
        que el docente decida su eliminación."""
        participant = self.get(user, participant_id)
        store = self._authorization_store()
        current = store.get(authorization_id)
        if current is None or current.participant_id != participant.id:
            raise ParticipantNotFound(authorization_id)
        party, scope = Grantor(party), RevokedScope(scope)
        is_child = participant.kind is ParticipantKind.CHILD
        if not is_child and (party is Grantor.GUARDIAN or scope is RevokedScope.ASSENT):
            raise ValueError("En un adulto, solo el propio participante retira su autorización")
        if current.revoked:
            return current
        revoked = store.revoke(replace(current, revoked_at=self.clock(), revoked_by_user_id=user.id,
                                       revoked_party=party, revoked_scope=scope))
        self.audit.record(user, AuditAction.AUTHORIZATION_CHANGE, AUTHORIZATION, revoked.id)
        return revoked

    def require_session(self, user: User, participant_id: str) -> Participant:
        """Comprueba que quien registró al participante puede iniciar una sesión con él."""
        participant = self.get(user, participant_id)
        if participant.registered_by_user_id != user.id:
            raise PermissionError("Solo quien registró al participante conduce sus sesiones")
        status = self.status(participant)
        if status == AuthorizationStatus.REVOKED:
            raise SessionNotAllowed("Se retiró una autorización de este participante: no se inician sesiones nuevas")
        if status == AuthorizationStatus.NO_AGE:
            raise SessionNotAllowed("Este participante no tiene edad registrada: regístralo de nuevo con su edad")
        if status != AuthorizationStatus.READY:
            raise SessionNotAllowed(
                "Falta la autorización firmada: participación y registro de la expresión estimada, uso de la "
                "cámara y, con niños, su asentimiento")
        return participant

    def record_session_start(self, user: User, session_id: str) -> None:
        self.audit.record(user, AuditAction.CREATE, SESSION, session_id)

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
