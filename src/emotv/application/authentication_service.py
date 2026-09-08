from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash

from emotv.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM
from emotv.application.ports.user_repository import UserRepository
from emotv.domain.user import User


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
        if len(password) < 12:
            raise ValueError("la contraseña debe tener al menos 12 caracteres")
        return self.passwords.hash(password)

    def authenticate(self, email: str, password: str) -> User | None:
        user = self.repository.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            return None
        return user if self.passwords.verify(password, user.password_hash) else None

    def create_access_token(self, user: User) -> str:
        now = self.clock()
        return jwt.encode(
            {"sub": user.id, "role": user.role.value, "iat": now,
             "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
            self.secret_key,
            algorithm=JWT_ALGORITHM,
        )

    def decode_access_token(self, token: str) -> dict[str, object]:
        return jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
