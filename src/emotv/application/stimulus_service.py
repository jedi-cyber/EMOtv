"""Banco de estímulos: lo gestionan los docentes (para los usuarios de su
grupo) y el administrador (para toda la institución). Los usuarios los usan,
pero no los crean.

Un estímulo nunca es una foto de una persona evaluada. Las imágenes abstractas son
de creación propia o con una licencia que lo permita; no se incluyen láminas de
pruebas proyectivas publicadas. El sistema solo muestra y registra: no
relaciona ninguna imagen con una condición.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.ports.practice_repositories import StimulusRepository
from emotv.domain.audit import AuditAction
from emotv.domain.role import Role
from emotv.domain.stimulus import Stimulus, StimulusKind, StimulusScope
from emotv.domain.user import User

RESOURCE = "stimulus"
ImageSanitizer = Callable[[bytes], tuple[str, bytes]]
DocenteOf = Callable[[str], str | None]


class StimulusNotFound(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class StimulusDraft:
    title: str
    kind: str
    category: str
    intensity: str
    min_age: int
    origin: str
    license: str
    expected_expression: str | None = None
    # Declaraciones de quien sube la imagen.
    not_a_participant_photo: bool = False
    not_a_projective_test: bool = False


class StimulusService:
    def __init__(
        self,
        repository: StimulusRepository,
        audit: AuditService,
        docente_of: DocenteOf,
        sanitize: ImageSanitizer,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.audit = audit
        self.docente_of = docente_of
        self.sanitize = sanitize
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Alcance -------------------------------------------------------------

    def _group_owners(self, user: User) -> tuple[str, ...]:
        """Docentes cuyos estímulos de grupo ve la cuenta."""
        if user.role is Role.STUDENT:
            docente = self.docente_of(user.id)
            return (docente,) if docente else ()
        if user.role is Role.PSYCHOLOGIST:
            return (user.id,)
        if user.role is Role.ADMIN:
            return ()
        raise PermissionError("El banco de estímulos es para docentes, usuarios y el administrador")

    def can_manage(self, user: User, stimulus: Stimulus) -> bool:
        if not user.is_active:
            return False
        if stimulus.scope is StimulusScope.INSTITUTION:
            return user.role is Role.ADMIN
        return user.role is Role.PSYCHOLOGIST and stimulus.owner_user_id == user.id

    def can_view(self, user: User, stimulus: Stimulus) -> bool:
        if self.can_manage(user, stimulus):
            return True
        try:
            owners = self._group_owners(user)
        except PermissionError:
            return False
        if user.role is Role.STUDENT and not stimulus.active:
            return False
        return stimulus.scope is StimulusScope.INSTITUTION or stimulus.owner_user_id in owners

    # --- Consulta ------------------------------------------------------------

    def list_for(self, user: User, for_children: bool = False) -> tuple[Stimulus, ...]:
        """Estímulos visibles. Con for_children, solo los que admite un protocolo
        para niños: leves, aprobados y vigentes."""
        items = tuple(item for item in self.repository.list_visible(self._group_owners(user))
                      if self.can_view(user, item))
        if for_children:
            items = tuple(item for item in items if item.suitable_for_children)
        return items

    def get(self, user: User, stimulus_id: str) -> Stimulus:
        stimulus = self.repository.get(stimulus_id)
        if stimulus is None or not self.can_view(user, stimulus):
            raise StimulusNotFound(stimulus_id)
        return stimulus

    def image(self, user: User, stimulus_id: str) -> tuple[str, bytes]:
        self.get(user, stimulus_id)
        found = self.repository.get_image(stimulus_id)
        if found is None:
            raise StimulusNotFound(stimulus_id)
        return found

    # --- Gestión -------------------------------------------------------------

    def create(self, user: User, draft: StimulusDraft, image: bytes) -> Stimulus:
        if user.role is Role.PSYCHOLOGIST:
            scope = StimulusScope.GROUP
        elif user.role is Role.ADMIN:
            scope = StimulusScope.INSTITUTION
        else:
            raise PermissionError("Los estímulos los crean los docentes y el administrador")
        if not draft.not_a_participant_photo:
            raise ValueError("Confirma que la imagen no es una fotografía de una persona")
        kind = StimulusKind(draft.kind)
        if kind is StimulusKind.ABSTRACT and not draft.not_a_projective_test:
            raise ValueError("Confirma que la imagen abstracta es de creación propia o con licencia que lo "
                             "permita, y que no es una lámina de una prueba proyectiva publicada")
        content_type, data = self.sanitize(image)
        stimulus = Stimulus(
            id=str(uuid4()), title=draft.title, kind=kind, category=draft.category,
            expected_expression=draft.expected_expression, intensity=draft.intensity, min_age=draft.min_age,
            origin=draft.origin, license=draft.license, scope=scope, owner_user_id=user.id,
            content_type=content_type, created_at=self.clock())
        self.repository.add(stimulus, data)
        self.audit.record(user, AuditAction.CREATE, RESOURCE, stimulus.id)
        return stimulus

    def _managed(self, user: User, stimulus_id: str) -> Stimulus:
        stimulus = self.repository.get(stimulus_id)
        if stimulus is None:
            raise StimulusNotFound(stimulus_id)
        if not self.can_manage(user, stimulus):
            raise PermissionError("Solo quien gestiona este estímulo puede cambiarlo")
        return stimulus

    def approve(self, user: User, stimulus_id: str) -> Stimulus:
        stimulus = self._managed(user, stimulus_id)
        if stimulus.approved:
            return stimulus
        approved = self.repository.save(replace(stimulus, approved_at=self.clock(), approved_by_user_id=user.id))
        self.audit.record(user, AuditAction.APPROVE, RESOURCE, stimulus.id)
        return approved

    def set_active(self, user: User, stimulus_id: str, active: bool) -> Stimulus:
        """Retira o vuelve a ofrecer un estímulo; los protocolos que ya lo usan lo conservan."""
        stimulus = self._managed(user, stimulus_id)
        if stimulus.active == active:
            return stimulus
        updated = self.repository.save(replace(stimulus, active=active))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, stimulus.id)
        return updated
