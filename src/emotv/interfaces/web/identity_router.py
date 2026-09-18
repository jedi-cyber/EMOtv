from dataclasses import replace
from datetime import datetime
import secrets
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from emotv.application import AuthenticationService, IdentityRegistrationService
from emotv.application.ports import UserRepository, StudentRepository, ConsentRepository
from emotv.domain import Role, User
from emotv.interfaces.web.auth_router import create_current_user_dependency, UserResponse


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    role: Role
    student_code: str | None = Field(default=None, min_length=1, max_length=64)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str | None = Field(default=None, min_length=3, max_length=320)
    role: Role | None = None
    is_active: bool | None = None


class StudentResponse(BaseModel):
    id: str
    user_id: str
    student_code: str


class CreatedUserResponse(UserResponse):
    temporary_password: str | None = None


class ConsentRequest(BaseModel):
    policy_version: str = Field(min_length=1, max_length=64)


class ConsentResponse(BaseModel):
    id: str
    student_id: str
    policy_version: str
    granted_at: datetime
    revoked_at: datetime | None


class ConsentPolicyResponse(BaseModel):
    version: str | None
    url: str | None
    available: bool


def create_identity_router(authentication: AuthenticationService | None,
                           users: UserRepository | None,
                           students: StudentRepository | None,
                           consents: ConsentRepository | None) -> APIRouter:
    router = APIRouter(tags=["identity"])
    current_user = create_current_user_dependency(authentication, users)

    def configured() -> IdentityRegistrationService:
        if authentication is None or users is None or students is None or consents is None:
            raise HTTPException(503, "Identidades no configuradas")
        return IdentityRegistrationService(users, students, consents, authentication)

    def require_admin(user: User) -> None:
        if user.role is not Role.ADMIN:
            raise HTTPException(403, "Se requiere administración")

    def student_access(student_id: str, user: User, *, write: bool = False):
        service = configured()
        student = service.students.get_by_id(student_id)
        if student is None:
            raise HTTPException(404, "Estudiante no encontrado")
        if user.role is Role.STUDENT and student.user_id != user.id:
            raise HTTPException(403, "No tienes acceso a este estudiante")
        if write and user.role is Role.PSYCHOLOGIST:
            raise HTTPException(403, "El consentimiento debe registrarlo el estudiante o administración")
        return student

    @router.get("/users", response_model=list[UserResponse])
    def list_users(user: User = Depends(current_user)):
        require_admin(user)
        return [UserResponse.from_domain(item) for item in configured().users.list_all()]

    @router.get("/users/{user_id}", response_model=UserResponse)
    def get_user(user_id: str, user: User = Depends(current_user)):
        require_admin(user)
        item = configured().users.get_by_id(user_id)
        if item is None:
            raise HTTPException(404, "Usuario no encontrado")
        return UserResponse.from_domain(item)

    @router.post("/users", response_model=CreatedUserResponse, status_code=201)
    def create_user(request: UserCreate, user: User = Depends(current_user)):
        require_admin(user)
        service = configured()
        temporary_password = secrets.token_urlsafe(24)
        try:
            if request.role is Role.STUDENT:
                if not request.student_code or not request.student_code.strip():
                    raise HTTPException(422, "student_code es obligatorio para estudiantes")
                item, _ = service.register_student(request.email, temporary_password, request.student_code,
                                                   must_change_password=True)
            else:
                if request.student_code is not None:
                    raise HTTPException(422, "student_code solo corresponde a estudiantes")
                item = service.register_user(request.email, temporary_password, request.role,
                                             must_change_password=True)
        except IntegrityError as error:
            raise HTTPException(409, "Correo o código ya registrado") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return CreatedUserResponse(**UserResponse.from_domain(item).model_dump(),
                                   temporary_password=temporary_password)

    @router.patch("/users/{user_id}", response_model=UserResponse)
    def update_user(user_id: str, request: UserUpdate, user: User = Depends(current_user)):
        require_admin(user)
        service = configured()
        item = service.users.get_by_id(user_id)
        if item is None:
            raise HTTPException(404, "Usuario no encontrado")
        changes = request.model_dump(exclude_none=True)
        role = changes.get("role", item.role)
        if role is not item.role and (role is Role.STUDENT or item.role is Role.STUDENT):
            raise HTTPException(409, "No se puede convertir un perfil estudiantil mediante cambio de rol")
        if item.id == user.id and (changes.get("is_active") is False or role is not Role.ADMIN):
            raise HTTPException(409, "No puedes desactivar tu cuenta ni retirar tu propio rol administrativo")
        try:
            updated = replace(item, **changes)
            existing = service.users.get_by_email(updated.email)
            if existing is not None and existing.id != item.id:
                raise HTTPException(409, "Correo ya registrado")
            service.users.save(updated)
        except IntegrityError as error:
            raise HTTPException(409, "Correo ya registrado") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return UserResponse.from_domain(updated)

    @router.post("/users/{user_id}/reset-password", response_model=CreatedUserResponse)
    def reset_password(user_id: str, user: User = Depends(current_user)):
        require_admin(user)
        if user_id == user.id:
            raise HTTPException(409, "Cambia tu propia contraseña desde tu cuenta")
        service = configured()
        target = service.users.get_by_id(user_id)
        if target is None:
            raise HTTPException(404, "Usuario no encontrado")
        temporary_password = secrets.token_urlsafe(24)
        updated = replace(target, password_hash=service.password_hasher.hash_password(temporary_password),
                          must_change_password=True, token_version=target.token_version + 1)
        service.users.save(updated)
        return CreatedUserResponse(**UserResponse.from_domain(updated).model_dump(),
                                   temporary_password=temporary_password)

    @router.delete("/users/{user_id}", response_model=UserResponse)
    def deactivate_user(user_id: str, user: User = Depends(current_user)):
        return update_user(user_id, UserUpdate(is_active=False), user)

    @router.get("/students", response_model=list[StudentResponse])
    def list_students(user: User = Depends(current_user)):
        service = configured()
        if user.role is Role.STUDENT:
            actor = service.students.get_by_user_id(user.id)
            items = (actor,) if actor else ()
        else:
            items = service.students.list_all()
        return [StudentResponse(id=item.id, user_id=item.user_id, student_code=item.student_code) for item in items]

    @router.get("/students/{student_id}", response_model=StudentResponse)
    def get_student(student_id: str, user: User = Depends(current_user)):
        item = student_access(student_id, user)
        return StudentResponse(id=item.id, user_id=item.user_id, student_code=item.student_code)

    def consent_response(item):
        return ConsentResponse(id=item.id, student_id=item.student_id, policy_version=item.policy_version,
                               granted_at=item.granted_at, revoked_at=item.revoked_at)

    def active_policy() -> ConsentPolicyResponse:
        version = os.getenv("CONSENT_POLICY_VERSION", "").strip()
        url = os.getenv("CONSENT_POLICY_URL", "").strip()
        available = bool(version and url and
                         (url.startswith("https://") or url.startswith("http://localhost") or
                          url.startswith("http://127.0.0.1")))
        return ConsentPolicyResponse(version=version if available else None,
                                     url=url if available else None, available=available)

    @router.get("/consent-policy", response_model=ConsentPolicyResponse)
    def get_consent_policy(user: User = Depends(current_user)):
        return active_policy()

    @router.get("/students/{student_id}/consents/active", response_model=ConsentResponse | None)
    def active_consent(student_id: str, user: User = Depends(current_user)):
        student_access(student_id, user)
        item = configured().consents.get_active_by_student(student_id)
        return consent_response(item) if item else None

    @router.get("/students/{student_id}/consents", response_model=list[ConsentResponse])
    def consent_history(student_id: str, user: User = Depends(current_user)):
        student_access(student_id, user)
        return [consent_response(item) for item in configured().consents.list_by_student(student_id)]

    @router.post("/students/{student_id}/consents", response_model=ConsentResponse, status_code=201)
    def grant_consent(student_id: str, request: ConsentRequest, user: User = Depends(current_user)):
        if user.role is not Role.STUDENT:
            raise HTTPException(403, "La aceptación debe realizarla el estudiante desde su cuenta")
        student_access(student_id, user, write=True)
        policy = active_policy()
        if not policy.available:
            raise HTTPException(503, "No hay una política de consentimiento aprobada y configurada")
        if request.policy_version != policy.version:
            raise HTTPException(409, "La versión de la política ha cambiado; revísala nuevamente")
        try:
            return consent_response(configured().grant_consent(student_id, request.policy_version))
        except (RuntimeError, IntegrityError) as error:
            raise HTTPException(409, "Ya existe un consentimiento activo") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.post("/students/{student_id}/consents/revoke", response_model=ConsentResponse)
    def revoke_consent(student_id: str, user: User = Depends(current_user)):
        student_access(student_id, user, write=True)
        try:
            return consent_response(configured().revoke_consent(student_id))
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error

    return router
