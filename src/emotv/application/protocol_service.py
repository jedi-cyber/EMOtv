"""Protocolos: recetas guardadas que dicen qué aplicar en una sesión
(cuestionario previo, imágenes con sus segundos y cuestionario posterior), para
un público de adultos o de niños.

El protocolo y sus cuestionarios no necesitan aprobación del docente. Uno para
niños solo admite imágenes leves y aprobadas. Una versión usada en una sesión
no se edita: editarla crea una versión nueva.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.ports.practice_repositories import ProtocolRepository
from emotv.application.questionnaire_service import QuestionnaireNotFound, QuestionnaireService
from emotv.application.stimulus_service import StimulusNotFound, StimulusService
from emotv.domain.audit import AuditAction
from emotv.domain.protocol import Protocol, ProtocolStep
from emotv.domain.role import Role
from emotv.domain.stimulus import StimulusKind
from emotv.domain.user import User

RESOURCE = "protocol"
DocenteOf = Callable[[str], str | None]
GroupUserIds = Callable[[str], Iterable[str]]


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
    post_questionnaire_id: str | None = None


class ProtocolService:
    def __init__(
        self,
        repository: ProtocolRepository,
        stimuli: StimulusService,
        audit: AuditService,
        docente_of: DocenteOf,
        group_user_ids: GroupUserIds,
        questionnaires: QuestionnaireService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.stimuli = stimuli
        self.audit = audit
        self.docente_of = docente_of
        self.group_user_ids = group_user_ids
        # Sin cuestionarios configurados no se acepta ninguno.
        self.questionnaires = questionnaires
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Acceso --------------------------------------------------------------

    @staticmethod
    def _require_conductor(user: User) -> None:
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            raise PermissionError("Los protocolos los arman usuarios y docentes")

    def can_view(self, user: User, protocol: Protocol) -> bool:
        """Quien lo armó y el docente de esa cuenta."""
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            return False
        if protocol.owner_user_id == user.id:
            return True
        return user.role is Role.PSYCHOLOGIST and self.docente_of(protocol.owner_user_id) == user.id

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
        for questionnaire_id in (draft.pre_questionnaire_id, draft.post_questionnaire_id):
            if questionnaire_id is None:
                continue
            try:
                if self.questionnaires is None:
                    raise QuestionnaireNotFound(questionnaire_id)
                self.questionnaires.get(user, questionnaire_id)
            except QuestionnaireNotFound as error:
                raise ValueError("Un cuestionario indicado no existe o no está disponible") from error
        for step in draft.steps:
            try:
                stimulus = self.stimuli.get(user, step.stimulus_id)
            except StimulusNotFound as error:
                raise ValueError("Un estímulo del protocolo no existe o no está disponible") from error
            if not stimulus.active:
                raise ValueError(f"El estímulo «{stimulus.title}» fue retirado del banco")
            if step.record_verbal_response and stimulus.kind is not StimulusKind.ABSTRACT:
                raise ValueError("Lo que la persona dice ver solo se registra en imágenes abstractas")
            if step.shown_before_analyzer and stimulus.kind is not StimulusKind.ABSTRACT:
                raise ValueError("Solo las imágenes abstractas se muestran antes del analizador")
            if draft.for_children and not stimulus.suitable_for_children:
                raise ValueError(f"Un protocolo para niños solo admite imágenes leves y aprobadas: «{stimulus.title}» "
                                 "no lo es")

    def create(self, user: User, draft: ProtocolDraft) -> Protocol:
        self._require_conductor(user)
        self._validate(user, draft)
        family = str(uuid4())
        protocol = self.repository.add(Protocol(
            id=family, family_id=family, version=1, owner_user_id=user.id, name=draft.name,
            description=draft.description, for_children=draft.for_children, created_at=self.clock(),
            steps=draft.steps, pre_questionnaire_id=draft.pre_questionnaire_id,
            post_questionnaire_id=draft.post_questionnaire_id))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, protocol.id)
        return protocol

    def edit(self, user: User, protocol_id: str, draft: ProtocolDraft) -> Protocol:
        """Una versión sin usar se reemplaza; una usada en una sesión no se
        toca y se crea la siguiente."""
        self._require_conductor(user)
        current = self.get(user, protocol_id)
        if current.owner_user_id != user.id:
            raise PermissionError("Solo quien armó el protocolo puede editarlo")
        if not current.current:
            raise ValueError("Esta versión ya fue reemplazada: edita la versión vigente")
        self._validate(user, draft)
        fields = dict(name=draft.name, description=draft.description, for_children=draft.for_children,
                      steps=draft.steps, pre_questionnaire_id=draft.pre_questionnaire_id,
                      post_questionnaire_id=draft.post_questionnaire_id,
                      approved_at=None, approved_by_user_id=None)
        if self.repository.is_used(current.id):
            now = self.clock()
            updated = self.repository.add_version(current.id, now, replace(
                current, id=str(uuid4()), version=current.version + 1, created_at=now, **fields))
        else:
            updated = self.repository.replace(replace(current, **fields))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, updated.id)
        return updated

    # --- Uso en una sesión ---------------------------------------------------

    def require_usable(self, user: User, protocol_id: str) -> Protocol:
        """Comprueba que quien conduce puede aplicar esta versión ahora. El
        público de la sesión es el del protocolo."""
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
        if protocol.for_children and any(not item.suitable_for_children for item in stimuli):
            raise ProtocolUnavailable("Un protocolo para niños solo admite imágenes leves y aprobadas")
        return protocol
