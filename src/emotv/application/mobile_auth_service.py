"""Inicio de sesión del aplicativo móvil: token de acceso corto y token de
renovación revocable.

Reutiliza AuthenticationService (contraseñas, firma de tokens) y LoginThrottle
(bloqueo por intentos fallidos). Solo usuarios y docentes inician sesión en el
aplicativo. El token de acceso lleva la audiencia ``emotv-mobile``: no sirve en
la web, y los de la web no sirven en el aplicativo. Cada token de acceso nombra
su sesión móvil (``sid``): al cerrar sesión o revocarla deja de valer aunque no
haya vencido. El token de renovación se guarda solo como SHA-256 y cambia en
cada renovación; si se vuelve a usar uno ya reemplazado, la sesión se revoca.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Protocol
from uuid import uuid4

import jwt

from emotv.application.audit_service import AuditService
from emotv.application.authentication_service import AuthenticationService
from emotv.application.login_throttle import LoginThrottle
from emotv.application.ports.user_repository import UserRepository
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.role import CONDUCTOR_ROLES
from emotv.domain.user import User

MOBILE_AUDIENCE = "emotv-mobile"
ACCESS_MINUTES = 15
REFRESH_DAYS = 30
RESOURCE = "mobile_session"


@dataclass(frozen=True, slots=True)
class MobileSession:
    id: str
    user_id: str
    refresh_token_hash: str
    token_version: int
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime
    previous_token_hash: str | None = None
    revoked_at: datetime | None = None


class MobileSessionRepository(Protocol):
    def add(self, session: MobileSession) -> MobileSession: ...
    def get(self, session_id: str) -> MobileSession | None: ...
    def by_refresh_hash(self, token_hash: str) -> MobileSession | None: ...
    def by_previous_hash(self, token_hash: str) -> MobileSession | None: ...
    def save(self, session: MobileSession) -> MobileSession: ...


@dataclass(frozen=True, slots=True)
class MobileTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    user: User


class MobileLoginError(Exception):
    """Inicio de sesión rechazado; ``code`` lo distingue en el contrato."""

    def __init__(self, status_code: int, code: str, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status_code, self.code, self.message, self.retry_after = status_code, code, message, retry_after


INVALID_CREDENTIALS = MobileLoginError(401, "invalid_credentials", "Correo o contraseña incorrectos")
INVALID_REFRESH = MobileLoginError(401, "invalid_refresh_token", "La sesión venció o se cerró. Inicia sesión de nuevo.")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MobileAuthService:
    def __init__(self, repository: MobileSessionRepository, authentication: AuthenticationService,
                 users: UserRepository, audit: AuditService, throttle: LoginThrottle | None = None,
                 clock: Callable[[], datetime] | None = None, access_minutes: float = ACCESS_MINUTES,
                 refresh_days: float = REFRESH_DAYS) -> None:
        self.repository = repository
        self.authentication = authentication
        self.users = users
        self.audit = audit
        self.throttle = throttle
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.access_minutes = access_minutes
        self.refresh_days = refresh_days

    def _issue(self, user: User, session: MobileSession) -> tuple[str, str, MobileSession]:
        refresh = secrets.token_urlsafe(48)
        now = self.clock()
        previous = session.refresh_token_hash if session.refresh_token_hash else None
        stored = replace(session, refresh_token_hash=hash_token(refresh), previous_token_hash=previous,
                         last_used_at=now)
        access = self.authentication.create_access_token(
            user, minutes=self.access_minutes, claims={"aud": MOBILE_AUDIENCE, "sid": session.id})
        return access, refresh, stored

    def _tokens(self, user: User, access: str, refresh: str, session: MobileSession) -> MobileTokens:
        remaining = int((session.expires_at - self.clock()).total_seconds())
        return MobileTokens(access, refresh, int(self.access_minutes * 60), max(0, remaining), user)

    def login(self, email: str, password: str, ip: str) -> MobileTokens:
        if self.throttle is not None and self.throttle.is_blocked(email, ip):
            raise MobileLoginError(429, "too_many_attempts",
                                   "Demasiados intentos de inicio de sesión. Espera unos minutos e inténtalo de nuevo.",
                                   retry_after=int(self.throttle.window.total_seconds()))
        user = self.authentication.authenticate(email, password)
        if self.throttle is not None:
            self.throttle.record(email, ip, success=user is not None)
        if user is None:
            raise INVALID_CREDENTIALS
        if user.role not in CONDUCTOR_ROLES:
            self.audit.record(user, AuditAction.LOGIN, RESOURCE, None, AuditResult.DENIED)
            raise MobileLoginError(403, "role_not_allowed", "El aplicativo es para usuarios y docentes.")
        if user.must_change_password:
            raise MobileLoginError(403, "password_change_required",
                                   "Debes cambiar tu contraseña provisional en la web antes de usar el aplicativo.")
        now = self.clock()
        session = MobileSession(id=str(uuid4()), user_id=user.id, refresh_token_hash="",
                                token_version=user.token_version, created_at=now,
                                expires_at=now + timedelta(days=self.refresh_days), last_used_at=now)
        access, refresh, stored = self._issue(user, session)
        stored = self.repository.add(replace(stored, previous_token_hash=None))
        self.audit.record(user, AuditAction.LOGIN, RESOURCE, stored.id)
        return self._tokens(user, access, refresh, stored)

    def refresh(self, refresh_token: str) -> MobileTokens:
        token_hash = hash_token(refresh_token or "")
        session = self.repository.by_refresh_hash(token_hash)
        if session is None:
            reused = self.repository.by_previous_hash(token_hash)
            if reused is not None and reused.revoked_at is None:
                # Un token ya reemplazado volvió a usarse: puede haberse copiado.
                self.repository.save(replace(reused, revoked_at=self.clock()))
                self.audit.record(None, AuditAction.LOGOUT, RESOURCE, reused.id, AuditResult.DENIED)
            raise INVALID_REFRESH
        user = self.users.get_by_id(session.user_id)
        if (session.revoked_at is not None or session.expires_at <= self.clock() or user is None
                or not user.is_active or user.role not in CONDUCTOR_ROLES
                or user.token_version != session.token_version):
            if session.revoked_at is None:
                self.repository.save(replace(session, revoked_at=self.clock()))
            raise INVALID_REFRESH
        access, refresh, stored = self._issue(user, session)
        return self._tokens(user, access, refresh, self.repository.save(stored))

    def logout(self, user: User, session_id: str) -> None:
        session = self.repository.get(session_id)
        if session is None or session.user_id != user.id:
            return
        if session.revoked_at is None:
            self.repository.save(replace(session, revoked_at=self.clock()))
        self.audit.record(user, AuditAction.LOGOUT, RESOURCE, session.id)

    def authenticate_access(self, token: str) -> tuple[User, str]:
        """Usuario y sesión móvil de un token de acceso; PermissionError si no vale."""
        try:
            claims = self.authentication.decode_access_token(token, audience=MOBILE_AUDIENCE)
        except jwt.InvalidTokenError as error:
            raise PermissionError("Token inválido") from error
        subject, session_id = claims.get("sub"), claims.get("sid")
        if not isinstance(subject, str) or not isinstance(session_id, str):
            raise PermissionError("Token inválido")
        user = self.users.get_by_id(subject)
        session = self.repository.get(session_id)
        if (user is None or not user.is_active or user.role not in CONDUCTOR_ROLES
                or claims.get("tv") != user.token_version or session is None or session.user_id != user.id
                or session.revoked_at is not None or session.expires_at <= self.clock()):
            raise PermissionError("Token inválido")
        return user, session_id
