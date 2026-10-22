"""Protocolos: secuencias de estímulos que arma quien conduce las sesiones.

Con adultos un protocolo se usa sin aprobación; con niños, solo cuando el
docente lo aprueba y todos sus estímulos son leves, aprobados y adecuados a la
edad. Una versión usada en una sesión no se edita: editarla crea una versión
nueva, que vuelve a pedir aprobación.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.ports.practice_repositories import ProtocolRepository
from emotv.application.stimulus_service import StimulusNotFound, StimulusService
from emotv.domain.audit import AuditAction
from emotv.domain.participant import Participant, ParticipantKind
from emotv.domain.protocol import Protocol, ProtocolStep
from emotv.domain.role import Role
from emotv.domain.stimulus import StimulusIntensity, StimulusKind
from emotv.domain.user import User

RESOURCE = "protocol"
DocenteOf = Callable[[str], str | None]
GroupUserIds = Callable[[str], Iterable[str]]
QuestionnaireExists = Callable[[User, str], bool]


class ProtocolNotFound(LookupError):
    pass


class ProtocolUnavailable(Exception):
    """El protocolo no se puede usar en esta sesión."""


@dataclass(frozen=True, slots=True)
class ProtocolDraft:
    name: str
    description: str
    for_children: bool
    steps: tuple[ProtocolStep, ...]
    pre_questionnaire_id: str | None = None


class ProtocolService:
    def __init__(
        self,
        repository: ProtocolRepository,
        stimuli: StimulusService,
        audit: AuditService,
        docente_of: DocenteOf,
        group_user_ids: GroupUserIds,
        questionnaire_exists: QuestionnaireExists | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.stimuli = stimuli
        self.audit = audit
        self.docente_of = docente_of
        self.group_user_ids = group_user_ids
        # Sin módulo de cuestionarios (P6A) no se acepta ningún cuestionario previo.
        self.questionnaire_exists = questionnaire_exists
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Acceso --------------------------------------------------------------

    @staticmethod
    def _require_conductor(user: User) -> None:
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            raise PermissionError("Los protocolos los arman usuarios y docentes")

    def _approver_of(self, protocol: Protocol) -> str | None:
        """El docente del autor; si el autor es docente, él mismo."""
        docente = self.docente_of(protocol.owner_user_id)
        return docente or None

    def can_view(self, user: User, protocol: Protocol) -> bool:
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            return False
        if protocol.owner_user_id == user.id:
            return True
        return user.role is Role.PSYCHOLOGIST and self._approver_of(protocol) == user.id

    def can_approve(self, user: User, protocol: Protocol) -> bool:
        if not user.is_active or user.role is not Role.PSYCHOLOGIST:
            return False
        return protocol.owner_user_id == user.id or self._approver_of(protocol) == user.id

    def list_for(self, user: User) -> tuple[Protocol, ...]:
        self._require_conductor(user)
        owners = (user.id,) if user.role is Role.STUDENT else (user.id, *self.group_user_ids(user.id))
        return tuple(item for item in self.repository.list_current(owners) if self.can_view(user, item))

    def get(self, user: User, protocol_id: str) -> Protocol:
        protocol = self.repository.get(protocol_id)
        if protocol is None or not self.can_view(user, protocol):
            raise ProtocolNotFound(protocol_id)
        return protocol

    def is_used(self, protocol: Protocol) -> bool:
        return self.repository.is_used(protocol.id)

    # --- Armado y versiones --------------------------------------------------

    def _validate(self, user: User, draft: ProtocolDraft) -> None:
        if draft.pre_questionnaire_id is not None and (
                self.questionnaire_exists is None or not self.questionnaire_exists(user, draft.pre_questionnaire_id)):
            raise ValueError("El cuestionario previo indicado no existe o no está disponible")
        for step in draft.steps:
            try:
                stimulus = self.stimuli.get(user, step.stimulus_id)
            except StimulusNotFound as error:
                raise ValueError("Un estímulo del protocolo no existe o no está disponible") from error
            if not stimulus.active:
                raise ValueError(f"El estímulo «{stimulus.title}» fue retirado del banco")
            if step.record_verbal_response and stimulus.kind is not StimulusKind.ABSTRACT:
                raise ValueError("Lo que el participante dice ver solo se registra en imágenes abstractas")
            if draft.for_children and not (stimulus.approved and stimulus.intensity is StimulusIntensity.MILD):
                raise ValueError(f"Con niños solo se usan estímulos leves y aprobados: «{stimulus.title}» no lo es")

    def create(self, user: User, draft: ProtocolDraft) -> Protocol:
        self._require_conductor(user)
        self._validate(user, draft)
        family = str(uuid4())
        protocol = self.repository.add(Protocol(
            id=family, family_id=family, version=1, owner_user_id=user.id, name=draft.name,
            description=draft.description, for_children=draft.for_children, created_at=self.clock(),
            steps=draft.steps, pre_questionnaire_id=draft.pre_questionnaire_id))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, protocol.id)
        return protocol

    def edit(self, user: User, protocol_id: str, draft: ProtocolDraft) -> Protocol:
        """Una versión sin usar se reemplaza; una usada en una sesión no se
        toca y se crea la siguiente. En ambos casos se pierde la aprobación."""
        self._require_conductor(user)
        current = self.get(user, protocol_id)
        if current.owner_user_id != user.id:
            raise PermissionError("Solo quien armó el protocolo puede editarlo")
        if not current.current:
            raise ValueError("Esta versión ya fue reemplazada: edita la versión vigente")
        self._validate(user, draft)
        fields = dict(name=draft.name, description=draft.description, for_children=draft.for_children,
                      steps=draft.steps, pre_questionnaire_id=draft.pre_questionnaire_id,
                      approved_at=None, approved_by_user_id=None)
        if self.repository.is_used(current.id):
            now = self.clock()
            updated = self.repository.add_version(current.id, now, replace(
                current, id=str(uuid4()), version=current.version + 1, created_at=now, **fields))
        else:
            updated = self.repository.replace(replace(current, **fields))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, updated.id)
        return updated

    def approve(self, user: User, protocol_id: str) -> Protocol:
        protocol = self.get(user, protocol_id)
        if not self.can_approve(user, protocol):
            raise PermissionError("Los protocolos para niños los aprueba el docente")
        if not protocol.for_children:
            raise ValueError("Solo los protocolos para niños requieren aprobación")
        if not protocol.current:
            raise ValueError("Esta versión ya fue reemplazada")
        if protocol.approved:
            return protocol
        approved = self.repository.replace(replace(protocol, approved_at=self.clock(), approved_by_user_id=user.id))
        self.audit.record(user, AuditAction.APPROVE, RESOURCE, protocol.id)
        return approved

    # --- Uso en una sesión ---------------------------------------------------

    def require_usable(self, user: User, protocol_id: str, participant: Participant | None) -> Protocol:
        """Comprueba que quien conduce puede aplicar esta versión al participante."""
        protocol = self.get(user, protocol_id)
        if protocol.owner_user_id != user.id:
            raise ProtocolUnavailable("Solo se aplican los protocolos que armaste")
        if not protocol.current:
            raise ProtocolUnavailable("Hay una versión más nueva de este protocolo")
        stimuli = []
        for step in protocol.steps:
            try:
                stimuli.append(self.stimuli.get(user, step.stimulus_id))
            except StimulusNotFound as error:
                raise ProtocolUnavailable("Un estímulo del protocolo ya no está disponible") from error
        if any(not item.active for item in stimuli):
            raise ProtocolUnavailable("Un estímulo del protocolo fue retirado del banco")
        if participant is not None and participant.kind is ParticipantKind.CHILD:
            if not protocol.for_children:
                raise ProtocolUnavailable("Este protocolo no está preparado para niños")
            if not protocol.approved:
                raise ProtocolUnavailable("Un protocolo para niños se usa solo cuando el docente lo aprueba")
            if any(not item.suitable_for_child(participant.age_years) for item in stimuli):
                raise ProtocolUnavailable("El protocolo tiene estímulos que no son adecuados para la edad del niño o "
                                          "la niña")
        return protocol
