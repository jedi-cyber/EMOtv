from __future__ import annotations

from dataclasses import replace
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from emotv.application import AuthenticationService, AuthorizationService
from emotv.application.login_throttle import LoginThrottle
from emotv.application.ports import UserRepository
from emotv.domain import AccessAction, User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    must_change_password: bool = False

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email, role=user.role.value,
                   is_active=user.is_active, must_change_password=user.must_change_password)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def create_current_user_dependency(
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    *,
    allow_password_change: bool = False,
):
    def current_user(token: str = Depends(oauth2_scheme)) -> User:
        if authentication is None or users is None:
            raise HTTPException(status_code=503, detail="Autenticación no configurada")
        unauthorized = HTTPException(
            status_code=401,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            claims = authentication.decode_access_token(token)
            subject = claims.get("sub")
            if not isinstance(subject, str):
                raise unauthorized
        except jwt.InvalidTokenError as error:
            raise unauthorized from error
        user = users.get_by_id(subject)
        if user is None or not user.is_active or claims.get("tv") != user.token_version:
            raise unauthorized
        if user.must_change_password and not allow_password_change:
            raise HTTPException(status_code=403, detail="Debes cambiar la contraseña provisional antes de continuar")
        return user
    return current_user


LOGIN_FAILED_DETAIL = "Correo o contraseña incorrectos"
# Igual para el límite por correo+IP y por IP: no revela cuál se alcanzó.
LOGIN_THROTTLED_DETAIL = "Demasiados intentos de inicio de sesión. Espera unos minutos e inténtalo de nuevo."


def client_ip(request: Request) -> str:
    # Detrás de nginx, uvicorn (--proxy-headers) ya resolvió la IP real.
    return request.client.host if request.client and request.client.host else "desconocida"


def create_auth_router(
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    authorization: AuthorizationService | None = None,
    login_throttle: LoginThrottle | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["authentication"])
    policy = authorization or AuthorizationService()
    current_user = create_current_user_dependency(authentication, users)
    onboarding_user = create_current_user_dependency(authentication, users, allow_password_change=True)

    def require_services() -> tuple[AuthenticationService, UserRepository]:
        if authentication is None or users is None:
            raise HTTPException(status_code=503, detail="Autenticación no configurada")
        return authentication, users

    @router.post("/token", response_model=TokenResponse)
    def login(request: Request, form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
        auth, _ = require_services()
        ip = client_ip(request)
        if login_throttle is not None and login_throttle.is_blocked(form.username, ip):
            raise HTTPException(
                status_code=429,
                detail=LOGIN_THROTTLED_DETAIL,
                headers={"Retry-After": str(int(login_throttle.window.total_seconds()))},
            )
        user = auth.authenticate(form.username, form.password)
        if login_throttle is not None:
            login_throttle.record(form.username, ip, success=user is not None)
        if user is None:
            raise HTTPException(
                status_code=401,
                detail=LOGIN_FAILED_DETAIL,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenResponse(access_token=auth.create_access_token(user))

    @router.get("/me", response_model=UserResponse)
    def me(user: User = Depends(onboarding_user)) -> UserResponse:
        return UserResponse.from_domain(user)

    @router.post("/change-password", response_model=TokenResponse)
    def change_password(request: ChangePasswordRequest, user: User = Depends(onboarding_user)) -> TokenResponse:
        auth, repository = require_services()
        if auth.authenticate(user.email, request.current_password) is None:
            raise HTTPException(400, "Contraseña actual incorrecta")
        try:
            auth.validate_new_password(user, request.new_password)
            updated = replace(user, password_hash=auth.hash_password(request.new_password),
                              must_change_password=False, token_version=user.token_version + 1)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        repository.save(updated)
        return TokenResponse(access_token=auth.create_access_token(updated))

    @router.get("/users", response_model=list[UserResponse])
    def list_users(user: User = Depends(current_user)) -> list[UserResponse]:
        _, repository = require_services()
        try:
            policy.require(user, AccessAction.MANAGE_USERS)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        return [UserResponse.from_domain(item) for item in repository.list_all()]

    return router
