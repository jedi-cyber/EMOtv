"""Segundo factor de las cuentas de gestión (superadmin y admin).

Quien robe la contraseña de una de estas cuentas podría restablecer la clave de
un docente y leer su grupo. Por eso, además de la contraseña, piden un código
de una aplicación autenticadora:

- al iniciar sesión: la contraseña correcta solo entrega un token de paso de
  5 minutos (audiencia propia; no sirve como token de acceso). La primera vez
  la cuenta configura la aplicación; después escribe el código;
- antes de cada acción que cambia cuentas o grupos (código del momento).

La clave TOTP se guarda cifrada con SENSITIVE_DATA_KEY y un código aceptado no
vuelve a servir. Si se pierde el celular, el soporte técnico la reinicia con
scripts/security/reset_mfa.py.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone

import jwt

from emotv.application import totp
from emotv.application.audit_service import AuditService
from emotv.application.authentication_service import AuthenticationService
from emotv.application.ports.user_repository import UserRepository
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.role import MANAGEMENT_ROLES
from emotv.domain.user import User
from emotv.shared.security.field_encryption import FieldCipher

MFA_AUDIENCE = "emotv-mfa"
PENDING_MINUTES = 5
RESOURCE = "mfa"


class MfaUnavailable(RuntimeError):
    """Sin SENSITIVE_DATA_KEY no se puede guardar la clave TOTP."""


def requires_mfa(user: User) -> bool:
    return user.role in MANAGEMENT_ROLES


class MfaService:
    def __init__(self, users: UserRepository, authentication: AuthenticationService,
                 cipher: FieldCipher | None, audit: AuditService | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.users = users
        self.authentication = authentication
        self.cipher = cipher
        self.audit = audit
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _cipher(self) -> FieldCipher:
        if self.cipher is None:
            raise MfaUnavailable("El segundo factor necesita SENSITIVE_DATA_KEY configurada en el servidor")
        return self.cipher

    def _record(self, user: User, action: AuditAction, result: AuditResult = AuditResult.SUCCESS) -> None:
        if self.audit is not None:
            self.audit.record(user, action, RESOURCE, None, result)

    # --- Token de paso -------------------------------------------------------

    def pending_token(self, user: User) -> str:
        self._cipher()  # sin clave de cifrado no se puede completar el ingreso
        return self.authentication.create_access_token(
            user, minutes=PENDING_MINUTES, claims={"aud": MFA_AUDIENCE})

    def pending_user(self, token: str) -> User | None:
        try:
            claims = self.authentication.decode_access_token(token, audience=MFA_AUDIENCE)
        except jwt.InvalidTokenError:
            return None
        user = self.users.get_by_id(str(claims.get("sub", "")))
        if user is None or not user.is_active or claims.get("tv") != user.token_version or not requires_mfa(user):
            return None
        return user

    # --- Configuración -------------------------------------------------------

    def begin_setup(self, user: User) -> tuple[str, str]:
        """Clave nueva y su enlace otpauth://. Solo mientras la cuenta no tenga
        la aplicación confirmada: una clave confirmada no se vuelve a mostrar."""
        if user.mfa_enabled:
            raise PermissionError("La aplicación autenticadora ya está configurada")
        if user.mfa_secret is not None:
            # Sin confirmar todavía: la misma clave, para que un reintento no deje
            # en la aplicación una clave que el servidor ya reemplazó.
            secret = self._cipher().decrypt(user.mfa_secret)
            return secret, totp.provisioning_uri(secret, user.email)
        secret = totp.generate_secret()
        self.users.save(replace(user, mfa_secret=self._cipher().encrypt(secret), mfa_enabled_at=None,
                                mfa_last_step=None))
        return secret, totp.provisioning_uri(secret, user.email)

    # --- Verificación --------------------------------------------------------

    def _accept(self, user: User, code: str, *, same_step: bool = False) -> User | None:
        """``same_step`` deja repetir el último código (varias peticiones de una
        misma confirmación); nunca uno anterior. El ingreso no lo permite."""
        if user.mfa_secret is None:
            return None
        secret = self._cipher().decrypt(user.mfa_secret)
        last = user.mfa_last_step
        after = last - 1 if same_step and last is not None else last
        step = totp.matching_step(secret, code, self.clock(), after=after)
        if step is None:
            return None
        updated = replace(user, mfa_last_step=max(step, last or step),
                          mfa_enabled_at=user.mfa_enabled_at or self.clock())
        self.users.save(updated)
        return updated

    def complete_login(self, user: User, code: str) -> User | None:
        """Código del inicio de sesión. La primera vez también confirma la
        aplicación recién configurada."""
        enabling = not user.mfa_enabled
        accepted = self._accept(user, code)
        if accepted is None:
            self._record(user, AuditAction.LOGIN, AuditResult.FAILURE)
            return None
        if enabling:
            self._record(accepted, AuditAction.UPDATE)
        self._record(accepted, AuditAction.LOGIN)
        return accepted

    def confirm(self, user: User, code: str | None) -> bool:
        """Código del momento antes de una acción que cambia cuentas o grupos."""
        if not requires_mfa(user):
            return True
        current = self.users.get_by_id(user.id)
        if current is None or not current.mfa_enabled or not code:
            return False
        if self._accept(current, code, same_step=True) is None:
            self._record(current, AuditAction.AUTHORIZATION_CHANGE, AuditResult.DENIED)
            return False
        return True
