from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import secrets
import jwt
from pwdlib import PasswordHash

from emotv.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM
from emotv.application.ports.user_repository import UserRepository
from emotv.domain.user import User

# El sistema ya exigía 12 caracteres; se mantiene (cumple el mínimo de 10).
MIN_PASSWORD_LENGTH = 12
_DUMMY_HASH: str | None = None


class AuthenticationService:
    def __init__(
        self,
        repository: UserRepository,
        secret_key: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY debe tener al menos 32 caracteres")
        self.repository, self.secret_key = repository, secret_key
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.passwords = PasswordHash.recommended()

    def hash_password(self, password: str) -> str:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
        return self.passwords.hash(password)

    def validate_new_password(self, user: User, new_password: str) -> None:
        """Política para cambios de contraseña, incluido el primer acceso."""

        if len(new_password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
        if new_password.strip().lower() == user.email.strip().lower():
            raise ValueError("La contraseña no puede ser igual a tu correo.")
        if self.passwords.verify(new_password, user.password_hash):
            raise ValueError("La nueva contraseña debe ser diferente de la anterior.")

    def authenticate(self, email: str, password: str) -> User | None:
        """Usuario inexistente, inactivo o clave incorrecta: mismo resultado y costo similar.

        Siempre se verifica un hash argon2 (uno ficticio si el usuario no
        existe) para que el tiempo de respuesta no revele qué correos existen.
        """

        user = self.repository.get_by_email(email.strip().lower())
        valid = self.passwords.verify(password, user.password_hash if user else self._dummy_hash())
        if user is None or not user.is_active or not valid:
            return None
        return user

    def _dummy_hash(self) -> str:
        global _DUMMY_HASH
        if _DUMMY_HASH is None:
            _DUMMY_HASH = self.passwords.hash(secrets.token_urlsafe(32))
        return _DUMMY_HASH

    def create_access_token(self, user: User) -> str:
        now = self.clock()
        return jwt.encode(
            {"sub": user.id, "role": user.role.value, "tv": user.token_version, "iat": now,
             "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
            self.secret_key,
            algorithm=JWT_ALGORITHM,
        )

    def decode_access_token(self, token: str) -> dict[str, object]:
        return jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
