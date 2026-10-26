"""Compromiso de confidencialidad y aviso reforzado sobre datos de menores.

Los textos viven en emotv/resources con su versión en el encabezado. Usuarios y
docentes aceptan el compromiso en su primer ingreso y cada vez que cambia la
versión; sin aceptarlo no inician sesiones.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from importlib import resources
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.ports.privacy_repositories import CommitmentRepository
from emotv.domain.audit import AuditAction
from emotv.domain.role import CONDUCTOR_ROLES
from emotv.domain.user import User

COMMITMENT = "commitment"
CHILD_NOTICE = "child_notice"
RESOURCE_FILES = {COMMITMENT: "confidentiality_commitment.md", CHILD_NOTICE: "child_data_notice.md"}


@dataclass(frozen=True, slots=True)
class VersionedText:
    kind: str
    version: str
    provisional: bool
    content: str


@lru_cache(maxsize=None)
def load_text(kind: str) -> VersionedText:
    raw = resources.files("emotv.resources").joinpath(RESOURCE_FILES[kind]).read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"{RESOURCE_FILES[kind]} requiere encabezado con versión")
    header, content = raw[4:].split("\n---\n", 1)
    meta = dict(line.split(":", 1) for line in header.splitlines() if ":" in line)
    version = meta.get("version", "").strip()
    if not version:
        raise ValueError(f"{RESOURCE_FILES[kind]} no declara su versión")
    return VersionedText(kind, version, meta.get("provisional", "").strip().lower() == "true", content.strip())


class CommitmentRequired(PermissionError):
    """La cuenta no aceptó la versión vigente del compromiso."""


class CommitmentService:
    def __init__(self, repository: CommitmentRepository, audit: AuditService | None = None,
                 clock: Callable[[], datetime] | None = None,
                 texts: Callable[[str], VersionedText] = load_text) -> None:
        self.repository = repository
        self.audit = audit
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.texts = texts

    def text(self, kind: str = COMMITMENT) -> VersionedText:
        return self.texts(kind)

    def has_accepted(self, user: User, kind: str = COMMITMENT) -> bool:
        return self.repository.has_accepted(user.id, kind, self.text(kind).version)

    def requires_acceptance(self, user: User) -> bool:
        return user.role in CONDUCTOR_ROLES and not self.has_accepted(user)

    def require(self, user: User) -> None:
        if self.requires_acceptance(user):
            raise CommitmentRequired("Debes aceptar el compromiso de confidencialidad vigente")

    def accept(self, user: User, version: str, kind: str = COMMITMENT) -> None:
        if user.role not in CONDUCTOR_ROLES:
            raise PermissionError("Solo usuarios y docentes aceptan el compromiso")
        current = self.text(kind)
        if version != current.version:
            raise ValueError("La versión del texto cambió; revísala nuevamente")
        if self.repository.has_accepted(user.id, kind, current.version):
            return
        self.repository.add(str(uuid4()), user.id, kind, current.version, self.clock())
        if self.audit is not None:
            action = AuditAction.COMMITMENT_ACCEPT if kind == COMMITMENT else AuditAction.CHILD_NOTICE_ACCEPT
            self.audit.record(user, action, kind, current.version)
