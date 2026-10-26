"""Imágenes propias: un usuario sube imágenes para sus protocolos y su docente
las revisa. Una imagen sin aprobar no se usa en ninguna parte.

Antes de guardar, cada imagen se reescribe sin metadatos y pasa por la
detección automática de personas (rostros y cuerpos), en memoria. Con
confianza alta se rechaza y no se guarda nada; con confianza intermedia se
guarda marcada «Revisar: posible persona». La detección no es infalible: el
docente revisa todas. Nunca se reconoce a nadie.

La auditoría registra cada lote, cada rechazo, cada decisión del docente, cada
eliminación y cada apertura de la vista ampliada, sin contenido.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.ports.practice_repositories import NoticeRepository, StimulusRepository
from emotv.application.stimulus_service import DocenteOf, ImageSanitizer, StimulusNotFound
from emotv.config import UserImageSettings
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.notice import UserNotice
from emotv.domain.protocol import Protocol
from emotv.domain.role import Role
from emotv.domain.stimulus import AUDIENCE_INTENSITY, Stimulus, StimulusAudience, StimulusKind, StimulusScope
from emotv.domain.user import User

RESOURCE = "user_image"
BATCH_RESOURCE = "image_batch"
MAX_BATCH = 20
PERSON_REJECTED = ("Esta imagen parece mostrar a una persona. Para evitar subir fotos de personas, las imágenes con "
                   "personas las agrega tu docente al banco institucional.")
OWN_IMAGE_CATEGORY = "Imagen propia"
OWN_IMAGE_LICENSE = "Declarada por quien la subió: tiene derecho a usarla"

PersonConfidence = Callable[[bytes], object]
GroupUserIds = Callable[[str], Iterable[str]]
ProtocolsUsing = Callable[[str], Iterable[Protocol]]
Decision = Literal["children", "adults", "delete"]


@dataclass(frozen=True, slots=True)
class ImageUpload:
    data: bytes
    title: str
    origin: str
    audience: str
    # «No es una foto de una persona que pueda identificarse, y tengo derecho a usarla».
    rights_confirmed: bool


@dataclass(frozen=True, slots=True)
class UploadResult:
    title: str
    accepted: bool
    image: Stimulus | None = None
    message: str | None = None


def _confidence(found: object) -> float:
    """El detector devuelve un número o un objeto con .confidence (rostro o cuerpo)."""
    return float(getattr(found, "confidence", found))


class UserImageService:
    def __init__(
        self,
        repository: StimulusRepository,
        notices: NoticeRepository,
        audit: AuditService,
        docente_of: DocenteOf,
        group_user_ids: GroupUserIds,
        sanitize: ImageSanitizer,
        detect_person: PersonConfidence,
        settings: UserImageSettings,
        protocols_using: ProtocolsUsing = lambda stimulus_id: (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.notices = notices
        self.audit = audit
        self.docente_of = docente_of
        self.group_user_ids = group_user_ids
        self.sanitize = sanitize
        self.detect_person = detect_person
        self.settings = settings
        self.protocols_using = protocols_using
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Acceso --------------------------------------------------------------

    def can_review(self, user: User, image: Stimulus) -> bool:
        return (user.is_active and user.role is Role.PSYCHOLOGIST and image.scope is StimulusScope.USER
                and image.deleted_at is None and self.docente_of(image.owner_user_id) == user.id)

    def can_view(self, user: User, image: Stimulus) -> bool:
        if image.scope is not StimulusScope.USER or image.deleted_at is not None or not user.is_active:
            return False
        return image.owner_user_id == user.id or self.can_review(user, image)

    def _get(self, user: User, image_id: str) -> Stimulus:
        image = self.repository.get(image_id)
        if image is None or not self.can_view(user, image):
            raise StimulusNotFound(image_id)
        return image

    # --- Subida --------------------------------------------------------------

    def upload(self, user: User, items: Sequence[ImageUpload]) -> tuple[str, tuple[UploadResult, ...]]:
        """Sube un lote. Cada imagen se acepta (pendiente de revisión) o se
        rechaza por separado; una rechazada no se guarda."""
        if not user.is_active or user.role is not Role.STUDENT:
            raise PermissionError("Las imágenes propias las suben los usuarios; los docentes y el administrador "
                                  "agregan las suyas en Estímulos")
        if self.docente_of(user.id) is None:
            raise ValueError("Necesitas un docente asignado para que revise tus imágenes")
        if not items:
            raise ValueError("Selecciona al menos una imagen")
        if len(items) > MAX_BATCH:
            raise ValueError(f"Sube como máximo {MAX_BATCH} imágenes a la vez")
        current = len(self.repository.list_user_images((user.id,)))
        if current + len(items) > self.settings.upload_limit_per_user:
            raise ValueError(f"Puedes tener hasta {self.settings.upload_limit_per_user} imágenes propias; ahora "
                             f"tienes {current}")
        for item in items:
            if not item.rights_confirmed:
                raise ValueError("Confirma en cada imagen que no es una foto de una persona que pueda "
                                 "identificarse y que tienes derecho a usarla")
            if not item.origin.strip():
                raise ValueError("Indica de dónde es cada imagen")
            if not item.title.strip():
                raise ValueError("Cada imagen necesita un nombre")
            StimulusAudience(item.audience)
        # Primero se revisan todas; si la detección no está disponible, no se guarda ninguna.
        checked = []
        for item in items:
            content_type, data = self.sanitize(item.data)
            checked.append((item, content_type, data, _confidence(self.detect_person(data))))
        batch_id = str(uuid4())
        now = self.clock()
        results = []
        for item, content_type, data, confidence in checked:
            if confidence >= self.settings.person_reject_confidence:
                # No se guarda nada de esta imagen.
                self.audit.record(user, AuditAction.REJECT, RESOURCE, batch_id, AuditResult.DENIED)
                results.append(UploadResult(item.title.strip(), False, message=PERSON_REJECTED))
                continue
            image = Stimulus(
                id=str(uuid4()), title=item.title, kind=StimulusKind.EMOTIONAL, category=OWN_IMAGE_CATEGORY,
                intensity=AUDIENCE_INTENSITY[item.audience], min_age=1, origin=item.origin,
                license=OWN_IMAGE_LICENSE, scope=StimulusScope.USER, owner_user_id=user.id,
                content_type=content_type, created_at=now,
                possible_person=confidence >= self.settings.person_review_confidence, upload_batch_id=batch_id)
            self.repository.add(image, data)
            results.append(UploadResult(image.title, True, image=image))
        self.audit.record(user, AuditAction.CREATE, BATCH_RESOURCE, batch_id)
        return batch_id, tuple(results)

    # --- Consulta ------------------------------------------------------------

    def list_own(self, user: User) -> tuple[Stimulus, ...]:
        if not user.is_active or user.role is not Role.STUDENT:
            raise PermissionError("Las imágenes propias son de los usuarios")
        return self.repository.list_user_images((user.id,))

    def review_list(self, user: User) -> tuple[Stimulus, ...]:
        """Imágenes propias de los usuarios del grupo del docente: pendientes y aprobadas."""
        if not user.is_active or user.role is not Role.PSYCHOLOGIST:
            raise PermissionError("Las imágenes las revisa el docente del usuario")
        return tuple(item for item in self.repository.list_user_images(tuple(self.group_user_ids(user.id)))
                     if self.can_review(user, item))

    def pending_count(self, user: User) -> int:
        return sum(1 for item in self.review_list(user) if item.pending)

    def image(self, user: User, image_id: str, preview: bool = False) -> tuple[str, bytes]:
        """El archivo, para quien la subió y su docente. preview: el docente
        abre la vista ampliada (se audita)."""
        self._get(user, image_id)
        found = self.repository.get_image(image_id)
        if found is None:
            raise StimulusNotFound(image_id)
        if preview:
            self.audit.record(user, AuditAction.VIEW, RESOURCE, image_id)
        return found

    # --- Revisión del docente -------------------------------------------------

    def decide(self, user: User, image_ids: Sequence[str], decision: Decision,
               reason: str | None = None) -> tuple[Stimulus, ...]:
        """«Para niños», «Para adultos» (aprueba o reclasifica) o «Eliminar» (borra
        el archivo y el registro; el usuario ve el motivo, si se indica)."""
        if not user.is_active or user.role is not Role.PSYCHOLOGIST:
            raise PermissionError("Las imágenes las revisa el docente del usuario")
        if decision not in ("children", "adults", "delete"):
            raise ValueError("Decisión no válida")
        ids = tuple(dict.fromkeys(image_ids))
        if not ids:
            raise ValueError("Selecciona al menos una imagen")
        images = []
        for image_id in ids:
            image = self.repository.get(image_id)
            if image is None or not self.can_view(user, image):
                raise StimulusNotFound(image_id)
            if not self.can_review(user, image):
                raise PermissionError("Solo el docente del usuario revisa sus imágenes")
            images.append(image)
        now = self.clock()
        reason = (reason or "").strip()[:300] or None
        updated = []
        for image in images:
            if decision == "delete":
                self._delete(user, image, now, reason)
                continue
            intensity = AUDIENCE_INTENSITY[decision]
            changed = replace(image, intensity=intensity, approved_at=image.approved_at or now,
                              approved_by_user_id=image.approved_by_user_id or user.id, expiry_notified_at=None)
            self.repository.save(changed)
            self.audit.record(user, AuditAction.APPROVE if image.pending else AuditAction.UPDATE, RESOURCE, image.id)
            if image.approved and decision == "adults" and image.audience is StimulusAudience.CHILDREN:
                for protocol in self.protocols_using(image.id):
                    if protocol.for_children:
                        self._notify(protocol.owner_user_id,
                                     f"El protocolo «{protocol.name}» necesita una imagen: tu docente marcó "
                                     f"«{image.title}» como «Para adultos» y ya no sirve en un protocolo para niños.")
            updated.append(changed)
        return tuple(updated)

    def _delete(self, actor: User | None, image: Stimulus, now: datetime, reason: str | None,
                message: str | None = None) -> None:
        affected = tuple(self.protocols_using(image.id))
        self.repository.remove(image.id, now)
        self.audit.record(actor, AuditAction.DELETE if actor else AuditAction.RETENTION_PURGE, RESOURCE, image.id)
        if message is None:
            message = f"Tu docente eliminó la imagen «{image.title}»."
            if reason:
                message += f" Motivo: {reason}"
        self._notify(image.owner_user_id, message)
        for protocol in affected:
            self._notify(protocol.owner_user_id,
                         f"El protocolo «{protocol.name}» necesita una imagen: «{image.title}» fue eliminada. "
                         "Elige otra para volver a usarlo.")

    # --- Vencimiento ---------------------------------------------------------

    def expire_pending(self) -> int:
        """Elimina las imágenes que nadie revisó en IMAGE_REVIEW_DAYS días, con
        un aviso previo al usuario. Devuelve cuántas se eliminaron."""
        now = self.clock()
        review = timedelta(days=self.settings.review_days)
        notice = timedelta(days=self.settings.expiry_notice_days)
        removed = 0
        for image in self.repository.list_pending():
            due = image.created_at + review
            if now >= due:
                self._delete(None, image, now, None,
                             message=f"Se eliminó la imagen «{image.title}» porque no se revisó en "
                                     f"{self.settings.review_days} días. Puedes volver a subirla.")
                removed += 1
            elif now >= due - notice and image.expiry_notified_at is None:
                self._notify(image.owner_user_id,
                             f"La imagen «{image.title}» se eliminará el {due:%d/%m/%Y} si tu docente no la revisa "
                             "antes.")
                self.repository.save(replace(image, expiry_notified_at=now))
        return removed

    # --- Avisos --------------------------------------------------------------

    def _notify(self, user_id: str, message: str) -> None:
        self.notices.add(UserNotice(id=str(uuid4()), user_id=user_id, message=message, created_at=self.clock()))

    def notices_for(self, user: User) -> tuple[UserNotice, ...]:
        return self.notices.list_unread(user.id)

    def mark_notice_read(self, user: User, notice_id: str) -> None:
        if not self.notices.mark_read(notice_id, user.id, self.clock()):
            raise StimulusNotFound(notice_id)
