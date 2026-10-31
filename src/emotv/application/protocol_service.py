"""Protocolos: recetas guardadas que dicen qué aplicar en una sesión
(cuestionario previo, imágenes con sus segundos y cuestionario posterior), para
un público de adultos o de niños.

El protocolo y sus cuestionarios no necesitan aprobación del docente. Uno para
niños solo admite imágenes «Para niños» (leves) y aprobadas; uno para adultos
admite las dos. Una imagen propia pendiente de revisión no se usa en ningún
protocolo. Una versión usada en una sesión no se edita: editarla crea una
versión nueva. Si el docente elimina o reclasifica una imagen que un protocolo
usa, el protocolo queda «Necesita una imagen» hasta que se reemplace.

Los protocolos de examen simulado no pasan por aquí: no se listan, no se editan
ni se aplican desde el Analizador. Los gestiona ExamService.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.practice_validation_service import VALIDATION_PROTOCOL_NAME, is_validation_protocol
from emotv.application.ports.practice_repositories import ProtocolRepository
from emotv.application.questionnaire_service import QuestionnaireNotFound, QuestionnaireService
from emotv.application.stimulus_service import StimulusNotFound, StimulusService
from emotv.domain.audit import AuditAction
from emotv.domain.protocol import Protocol, ProtocolKind, ProtocolStep
from emotv.domain.role import Role
from emotv.domain.stimulus import Stimulus, StimulusKind, StimulusScope
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
        validation_usable: Callable[[Protocol], bool] | None = None,
    ) -> None:
        self.repository = repository
        # El protocolo «Validación con adultos» solo se aplica en modo demo y con
        # cuentas de voluntarios (PracticeValidationService.usable).
        self.validation_usable = validation_usable or (lambda protocol: False)
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
        """Quien lo armó y el docente de esa cuenta. Un examen no es un protocolo de práctica."""
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            return False
        if protocol.kind is not ProtocolKind.PRACTICE:
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

    @staticmethod
    def _image_problem(protocol: Protocol, stimulus: Stimulus | None) -> str | None:
        """Por qué una imagen no sirve en este protocolo, o None si sirve."""
        if stimulus is None or stimulus.deleted_at is not None:
            return "Una imagen del protocolo fue eliminada"
        if stimulus.scope is StimulusScope.USER and stimulus.owner_user_id != protocol.owner_user_id:
            return "Una imagen propia solo se usa en los protocolos de quien la subió"
        if stimulus.pending:
            return f"La imagen «{stimulus.title}» todavía está en revisión"
        if not stimulus.usable:
            return f"El estímulo «{stimulus.title}» fue retirado del banco"
        if protocol.for_children and not stimulus.suitable_for_children:
            return (f"Un protocolo para niños solo admite imágenes leves y aprobadas «Para niños»: "
                    f"«{stimulus.title}» no lo es")
        return None

    def needs_image(self, protocol: Protocol) -> bool:
        """Algún paso nombra una imagen eliminada, sin aprobar, retirada o que ya
        no corresponde al público del protocolo."""
        return any(self._image_problem(protocol, self.stimuli.repository.get(step.stimulus_id)) is not None
                   for step in protocol.steps if step.stimulus_id is not None)

    # --- Armado y versiones --------------------------------------------------

    def _validate(self, user: User, draft: ProtocolDraft) -> None:
        target = Protocol(id="validacion", family_id="validacion", version=1, owner_user_id=user.id,
                          name=draft.name or "validacion", description=draft.description,
                          for_children=draft.for_children, created_at=self.clock(), steps=draft.steps)
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
            if step.stimulus_id is None:
                continue  # Ejercicio de práctica sin ilustración.
            try:
                stimulus = self.stimuli.get(user, step.stimulus_id)
            except StimulusNotFound as error:
                raise ValueError("Un estímulo del protocolo no existe o no está disponible") from error
            problem = self._image_problem(target, stimulus)
            if problem is not None:
                raise ValueError(problem)
            if step.record_verbal_response and stimulus.kind is not StimulusKind.ABSTRACT:
                raise ValueError("Lo que la persona dice ver solo se registra en imágenes abstractas")
            if step.shown_before_analyzer and stimulus.kind is not StimulusKind.ABSTRACT:
                raise ValueError("Solo las imágenes abstractas se muestran antes del analizador")

    @staticmethod
    def _reserved_name(name: str) -> None:
        if name.strip().casefold() == VALIDATION_PROTOCOL_NAME.casefold():
            raise ValueError(f"El nombre «{VALIDATION_PROTOCOL_NAME}» está reservado para el protocolo de validación")

    def create(self, user: User, draft: ProtocolDraft) -> Protocol:
        self._require_conductor(user)
        self._reserved_name(draft.name)
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
        if not is_validation_protocol(current):
            self._reserved_name(draft.name)
        elif draft.name.strip().casefold() != VALIDATION_PROTOCOL_NAME.casefold():
            raise ValueError("El protocolo de validación conserva su nombre")
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
        if is_validation_protocol(protocol) and not self.validation_usable(protocol):
            raise ProtocolUnavailable("El protocolo de validación solo se aplica en modo demo, con una cuenta "
                                      "de voluntario")
        for step in protocol.steps:
            if step.stimulus_id is None:
                continue  # práctica sin ilustración: no necesita imagen
            try:
                stimulus = self.stimuli.get(user, step.stimulus_id)
            except StimulusNotFound as error:
                raise ProtocolUnavailable("El protocolo necesita una imagen: una de sus imágenes ya no "
                                          "está disponible") from error
            problem = self._image_problem(protocol, stimulus)
            if problem is not None:
                raise ProtocolUnavailable(f"El protocolo necesita una imagen. {problem}")
        return protocol
