from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from emotv.application import AuthenticationService, AuthorizationService
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

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email, role=user.role.value,
                   is_active=user.is_active)


def create_current_user_dependency(
    authentication: AuthenticationService | None,
    users: UserRepository | None,
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
        if user is None or not user.is_active:
            raise unauthorized
        return user
    return current_user


def create_auth_router(
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    authorization: AuthorizationService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["authentication"])
    policy = authorization or AuthorizationService()
    current_user = create_current_user_dependency(authentication, users)

    def require_services() -> tuple[AuthenticationService, UserRepository]:
        if authentication is None or users is None:
            raise HTTPException(status_code=503, detail="Autenticación no configurada")
        return authentication, users

    @router.post("/token", response_model=TokenResponse)
    def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
        auth, _ = require_services()
        user = auth.authenticate(form.username, form.password)
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Correo o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenResponse(access_token=auth.create_access_token(user))

    @router.get("/me", response_model=UserResponse)
    def me(user: User = Depends(current_user)) -> UserResponse:
        return UserResponse.from_domain(user)

    @router.get("/users", response_model=list[UserResponse])
    def list_users(user: User = Depends(current_user)) -> list[UserResponse]:
        _, repository = require_services()
        try:
            policy.require(user, AccessAction.MANAGE_USERS)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        return [UserResponse.from_domain(item) for item in repository.list_all()]

    return router
