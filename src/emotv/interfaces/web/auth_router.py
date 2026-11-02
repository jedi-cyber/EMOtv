from __future__ import annotations

from dataclasses import replace
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from emotv.application import AuthenticationService, AuthorizationService
from emotv.application.login_throttle import LoginThrottle
from emotv.application.mfa_service import MfaService, MfaUnavailable, requires_mfa
from emotv.application.ports import UserRepository
from emotv.domain import AccessAction, Role, User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class TokenResponse(BaseModel):
    # Vacío mientras una cuenta de gestión no escriba el código de su aplicación.
    access_token: str | None = None
    token_type: str = "bearer"
    # Cuentas de gestión: "setup" (configurar la aplicación) o "verify" (escribir el código).
    mfa: str | None = None
    mfa_token: str | None = None


class MfaTokenRequest(BaseModel):
    mfa_token: str


class MfaCodeRequest(BaseModel):
    mfa_token: str
    code: str


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    must_change_password: bool = False
    # Otra cuenta restableció la contraseña: se avisa en el siguiente ingreso.
    password_reset: bool = False

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email, role=user.role.value,
                   is_active=user.is_active, must_change_password=user.must_change_password,
                   password_reset=user.password_reset_at is not None)


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
# Las cuentas de gestión se bloquean antes: contraseña y código cuentan juntos.
PRIVILEGED_MAX_FAILURES = 3
MFA_EXPIRED_DETAIL = "El ingreso venció. Escribe de nuevo tu correo y contraseña."
MFA_CODE_DETAIL = "Código incorrecto o ya usado. Escribe el código que muestra ahora tu aplicación."


def client_ip(request: Request) -> str:
    # Detrás de nginx, uvicorn (--proxy-headers) ya resolvió la IP real.
    return request.client.host if request.client and request.client.host else "desconocida"


def create_auth_router(
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    authorization: AuthorizationService | None = None,
    login_throttle: LoginThrottle | None = None,
    mfa: MfaService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["authentication"])
    policy = authorization or AuthorizationService()
    current_user = create_current_user_dependency(authentication, users)
    onboarding_user = create_current_user_dependency(authentication, users, allow_password_change=True)

    def require_services() -> tuple[AuthenticationService, UserRepository]:
        if authentication is None or users is None:
            raise HTTPException(status_code=503, detail="Autenticación no configurada")
        return authentication, users

    def is_privileged(email: str) -> bool:
        try:
            account = users.get_by_email(email) if users is not None else None
        except ValueError:
            return False
        return account is not None and requires_mfa(account)

    def check_throttle(email: str, ip: str) -> None:
        strict = PRIVILEGED_MAX_FAILURES if is_privileged(email) else None
        if login_throttle is not None and login_throttle.is_blocked(email, ip, max_account_failures=strict):
            raise HTTPException(
                status_code=429,
                detail=LOGIN_THROTTLED_DETAIL,
                headers={"Retry-After": str(int(login_throttle.window.total_seconds()))},
            )

    def require_mfa() -> MfaService:
        if mfa is None:
            raise HTTPException(503, "El segundo factor no está configurado en el servidor")
        return mfa

    @router.post("/token", response_model=TokenResponse, response_model_exclude_none=True)
    def login(request: Request, form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
        auth, _ = require_services()
        ip = client_ip(request)
        check_throttle(form.username, ip)
        user = auth.authenticate(form.username, form.password)
        # En una cuenta de gestión el acceso correcto se registra al aceptar el
        # código: si se registrara aquí, reiniciaría el contador de códigos fallidos.
        if login_throttle is not None and (user is None or not requires_mfa(user)):
            login_throttle.record(form.username, ip, success=user is not None)
        if user is None:
            raise HTTPException(
                status_code=401,
                detail=LOGIN_FAILED_DETAIL,
                headers={"WWW-Authenticate": "Bearer"},
            )
        if requires_mfa(user):
            try:
                pending = require_mfa().pending_token(user)
            except MfaUnavailable as error:
                raise HTTPException(503, str(error)) from error
            return TokenResponse(mfa="verify" if user.mfa_enabled else "setup", mfa_token=pending)
        return TokenResponse(access_token=auth.create_access_token(user))

    def pending_user(token: str) -> User:
        user = require_mfa().pending_user(token)
        if user is None:
            raise HTTPException(401, MFA_EXPIRED_DETAIL)
        return user

    @router.post("/mfa/setup", response_model=MfaSetupResponse)
    def mfa_setup(request: MfaTokenRequest) -> MfaSetupResponse:
        """Primera vez: clave para la aplicación autenticadora. Se muestra una sola vez."""
        service, user = require_mfa(), pending_user(request.mfa_token)
        try:
            secret, uri = service.begin_setup(user)
        except PermissionError as error:
            raise HTTPException(409, str(error)) from error
        except MfaUnavailable as error:
            raise HTTPException(503, str(error)) from error
        return MfaSetupResponse(secret=secret, otpauth_uri=uri)

    @router.post("/mfa/verify", response_model=TokenResponse, response_model_exclude_none=True)
    def mfa_verify(request: Request, body: MfaCodeRequest) -> TokenResponse:
        auth, _ = require_services()
        service, user = require_mfa(), pending_user(body.mfa_token)
        ip = client_ip(request)
        check_throttle(user.email, ip)
        try:
            accepted = service.complete_login(user, body.code)
        except MfaUnavailable as error:
            raise HTTPException(503, str(error)) from error
        if login_throttle is not None:
            login_throttle.record(user.email, ip, success=accepted is not None)
        if accepted is None:
            raise HTTPException(401, MFA_CODE_DETAIL)
        return TokenResponse(access_token=auth.create_access_token(accepted))

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
            # La persona ya vio el aviso de restablecimiento al cambiarla.
            updated = replace(user, password_hash=auth.hash_password(request.new_password),
                              must_change_password=False, token_version=user.token_version + 1,
                              password_reset_at=None)
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
        # Cada papel de gestión ve solo las cuentas que gestiona.
        visible = {Role.SUPERADMIN: {Role.ADMIN}, Role.ADMIN: {Role.PSYCHOLOGIST, Role.STUDENT}}.get(user.role, set())
        return [UserResponse.from_domain(item) for item in repository.list_all() if item.role in visible]

    return router
