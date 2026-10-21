from dataclasses import replace
from datetime import datetime
import secrets
import os
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from emotv.application import AuthenticationService, IdentityRegistrationService
from emotv.application.consent_policy_service import ConsentPolicyService
from emotv.domain.consent_policy import ConsentPolicy
from emotv.application.ports import UserRepository, StudentRepository, ConsentRepository
from emotv.application.ports.assignment_repository import AssignmentRepository
from emotv.domain import Role, User
from emotv.domain.psychologist_assignment import PsychologistAssignment
from emotv.interfaces.web.auth_router import create_current_user_dependency, UserResponse
from emotv.application.audit_service import AuditService
from emotv.config import PrivacySettings
from emotv.domain.audit import AuditAction, AuditResult


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


class AssignedStudentResponse(StudentResponse):
    assigned_at: datetime


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
    id: str | None = None
    code: str | None = None
    version: str | None
    title: str | None = None
    content: str | None = None
    effective_at: datetime | None = None
    is_demo: bool = False
    approved: bool = False
    mode: str = "production"
    url: str | None
    available: bool


class ConsentPolicyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    version: str = Field(min_length=1, max_length=16)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=30, max_length=16000)
    effective_at: datetime
    approved: bool = False


MANAGEABLE_ROLES: dict[Role, frozenset[Role]] = {
    # El superadministrador gestiona solo la cuenta de administrador.
    Role.SUPERADMIN: frozenset({Role.ADMIN}),
    # El administrador gestiona docentes y usuarios.
    Role.ADMIN: frozenset({Role.PSYCHOLOGIST, Role.STUDENT}),
}


def create_identity_router(authentication: AuthenticationService | None,
                           users: UserRepository | None,
                           students: StudentRepository | None,
                           consents: ConsentRepository | None,
                           policy_service: ConsentPolicyService | None = None,
                           assignments: AssignmentRepository | None = None,
                           audit: AuditService | None = None,
                           privacy: PrivacySettings | None = None) -> APIRouter:
    router = APIRouter(tags=["identity"])
    current_user = create_current_user_dependency(authentication, users)
    limits = privacy or PrivacySettings()

    def configured() -> IdentityRegistrationService:
        if authentication is None or users is None or students is None or consents is None:
            raise HTTPException(503, "Identidades no configuradas")
        return IdentityRegistrationService(users, students, consents, authentication)

    def record(actor: User, action: AuditAction, resource_type: str, resource_id: str | None,
               result: AuditResult = AuditResult.SUCCESS) -> None:
        if audit is not None:
            audit.record(actor, action, resource_type, resource_id, result)

    def manageable(user: User) -> frozenset[Role]:
        roles = MANAGEABLE_ROLES.get(user.role, frozenset())
        if not roles:
            raise HTTPException(403, "Tu cuenta no gestiona otras cuentas")
        return roles

    def require_superadmin(user: User) -> None:
        if user.role is not Role.SUPERADMIN:
            raise HTTPException(403, "Se requiere el superadministrador")

    def require_admin(user: User) -> None:
        if user.role is not Role.ADMIN:
            raise HTTPException(403, "Se requiere el administrador")

    def managed_target(user: User, user_id: str) -> User:
        roles = manageable(user)
        item = configured().users.get_by_id(user_id)
        if item is None or item.role not in roles:
            # Sin revelar si existe una cuenta que no le corresponde gestionar.
            raise HTTPException(404, "Cuenta no encontrada")
        return item

    def active_admins(service: IdentityRegistrationService) -> int:
        return sum(1 for item in service.users.list_all() if item.role is Role.ADMIN and item.is_active)

    def require_admin_slot(service: IdentityRegistrationService) -> None:
        if active_admins(service) >= limits.max_admin_accounts:
            raise HTTPException(409, "Ya existe el máximo de cuentas de administrador activas "
                                     f"({limits.max_admin_accounts}). Desactiva la actual antes de crear otra.")

    def is_assigned(psychologist_user_id: str, student_id: str) -> bool:
        return assignments is not None and assignments.is_assigned(psychologist_user_id, student_id)

    def student_access(student_id: str, user: User, *, write: bool = False):
        service = configured()
        student = service.students.get_by_id(student_id)
        if student is None:
            raise HTTPException(404, "Usuario no encontrado")
        if user.role in (Role.ADMIN, Role.SUPERADMIN):
            raise HTTPException(403, "Esta información la consultan el usuario y su docente")
        if user.role is Role.STUDENT and student.user_id != user.id:
            raise HTTPException(403, "No tienes acceso a este usuario")
        if user.role is Role.PSYCHOLOGIST and not is_assigned(user.id, student.id):
            raise HTTPException(403, "Este usuario no pertenece a tu grupo")
        if write and user.role is Role.PSYCHOLOGIST:
            raise HTTPException(403, "El consentimiento lo registra el usuario desde su cuenta")
        return student

    @router.get("/users", response_model=list[UserResponse])
    def list_users(user: User = Depends(current_user)):
        roles = manageable(user)
        return [UserResponse.from_domain(item) for item in configured().users.list_all() if item.role in roles]

    @router.get("/users/{user_id}", response_model=UserResponse)
    def get_user(user_id: str, user: User = Depends(current_user)):
        return UserResponse.from_domain(managed_target(user, user_id))

    @router.post("/users", response_model=CreatedUserResponse, status_code=201)
    def create_user(request: UserCreate, user: User = Depends(current_user)):
        if request.role not in manageable(user):
            raise HTTPException(403, "Tu cuenta no puede crear cuentas con ese papel")
        service = configured()
        if request.role is Role.ADMIN:
            require_admin_slot(service)
        temporary_password = secrets.token_urlsafe(24)
        try:
            if request.role is Role.STUDENT:
                if not request.student_code or not request.student_code.strip():
                    raise HTTPException(422, "El código de usuario es obligatorio")
                item, _ = service.register_student(request.email, temporary_password, request.student_code,
                                                   must_change_password=True)
            else:
                if request.student_code is not None:
                    raise HTTPException(422, "El código solo corresponde a cuentas de usuario")
                item = service.register_user(request.email, temporary_password, request.role,
                                             must_change_password=True)
        except IntegrityError as error:
            raise HTTPException(409, "Correo o código ya registrado") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        record(user, AuditAction.ACCOUNT_CREATE, "user", item.id)
        # La contraseña temporal se muestra una sola vez y nunca se guarda en claro.
        return CreatedUserResponse(**UserResponse.from_domain(item).model_dump(),
                                   temporary_password=temporary_password)

    @router.patch("/users/{user_id}", response_model=UserResponse)
    def update_user(user_id: str, request: UserUpdate, user: User = Depends(current_user)):
        item = managed_target(user, user_id)
        service = configured()
        changes = request.model_dump(exclude_none=True)
        if changes.get("role", item.role) is not item.role:
            raise HTTPException(409, "El papel de una cuenta no se cambia; crea una cuenta nueva")
        changes.pop("role", None)
        deactivating = changes.get("is_active") is False and item.is_active
        reactivating = changes.get("is_active") is True and not item.is_active
        if reactivating and item.role is Role.ADMIN:
            require_admin_slot(service)
        try:
            updated = replace(item, **changes)
            existing = service.users.get_by_email(updated.email)
            if existing is not None and existing.id != item.id:
                raise HTTPException(409, "Correo ya registrado")
            if deactivating:
                # Desactivar invalida los tokens vigentes.
                updated = replace(updated, token_version=item.token_version + 1)
            service.users.save(updated)
        except IntegrityError as error:
            raise HTTPException(409, "Correo ya registrado") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if deactivating:
            record(user, AuditAction.ACCOUNT_DEACTIVATE, "user", item.id)
        elif reactivating:
            record(user, AuditAction.ACCOUNT_REACTIVATE, "user", item.id)
        return UserResponse.from_domain(updated)

    @router.post("/users/{user_id}/reset-password", response_model=CreatedUserResponse)
    def reset_password(user_id: str, user: User = Depends(current_user)):
        target = managed_target(user, user_id)
        service = configured()
        temporary_password = secrets.token_urlsafe(24)
        updated = replace(target, password_hash=service.password_hasher.hash_password(temporary_password),
                          must_change_password=True, token_version=target.token_version + 1,
                          password_reset_at=datetime.now(timezone.utc))
        service.users.save(updated)
        record(user, AuditAction.PASSWORD_RESET, "user", target.id)
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
        elif user.role is Role.PSYCHOLOGIST:
            assigned = assignments.list_by_psychologist(user.id) if assignments is not None else ()
            items = tuple(item for item in (service.students.get_by_id(a.student_id) for a in assigned) if item)
        elif user.role is Role.ADMIN:
            # Solo datos de cuenta para armar los grupos; nunca sesiones ni resultados.
            items = service.students.list_all()
        else:
            raise HTTPException(403, "El superadministrador no gestiona usuarios")
        return [StudentResponse(id=item.id, user_id=item.user_id, student_code=item.student_code) for item in items]

    def assignment_services(user: User, psychologist_user_id: str) -> tuple[AssignmentRepository, User]:
        require_admin(user)
        service = configured()
        if assignments is None:
            raise HTTPException(503, "Grupos no configurados")
        psychologist = service.users.get_by_id(psychologist_user_id)
        if psychologist is None:
            raise HTTPException(404, "Cuenta no encontrada")
        if psychologist.role is not Role.PSYCHOLOGIST:
            raise HTTPException(422, "Los usuarios solo se asignan a cuentas de docente")
        return assignments, psychologist

    def assigned_response(assignment: PsychologistAssignment) -> AssignedStudentResponse | None:
        student = configured().students.get_by_id(assignment.student_id)
        if student is None:
            return None
        return AssignedStudentResponse(id=student.id, user_id=student.user_id, student_code=student.student_code,
                                       assigned_at=assignment.assigned_at)

    @router.get("/users/{user_id}/assigned-students", response_model=list[AssignedStudentResponse])
    def list_assigned_students(user_id: str, user: User = Depends(current_user)):
        repository, psychologist = assignment_services(user, user_id)
        items = (assigned_response(item) for item in repository.list_by_psychologist(psychologist.id))
        return [item for item in items if item is not None]

    @router.put("/users/{user_id}/assigned-students/{student_id}", response_model=AssignedStudentResponse)
    def assign_student(user_id: str, student_id: str, user: User = Depends(current_user)):
        """Agrega el usuario al grupo del docente; si tenía otro docente, lo mueve."""
        repository, psychologist = assignment_services(user, user_id)
        if configured().students.get_by_id(student_id) is None:
            raise HTTPException(404, "Usuario no encontrado")
        previous = repository.get_by_student(student_id)
        assignment = repository.assign(PsychologistAssignment(
            psychologist.id, student_id, datetime.now(timezone.utc), assigned_by_user_id=user.id))
        if previous is None or previous.psychologist_user_id != psychologist.id:
            record(user, AuditAction.GROUP_CHANGE, "student", student_id)
        return assigned_response(assignment)

    @router.delete("/users/{user_id}/assigned-students/{student_id}", status_code=204)
    def unassign_student(user_id: str, student_id: str, user: User = Depends(current_user)):
        repository, psychologist = assignment_services(user, user_id)
        if not repository.unassign(psychologist.id, student_id):
            raise HTTPException(404, "El usuario no pertenecía al grupo de este docente")
        record(user, AuditAction.GROUP_CHANGE, "student", student_id)
        return Response(status_code=204)

    @router.get("/students/{student_id}", response_model=StudentResponse)
    def get_student(student_id: str, user: User = Depends(current_user)):
        item = student_access(student_id, user)
        return StudentResponse(id=item.id, user_id=item.user_id, student_code=item.student_code)

    def consent_response(item):
        return ConsentResponse(id=item.id, student_id=item.student_id, policy_version=item.policy_version,
                               granted_at=item.granted_at, revoked_at=item.revoked_at)

    def active_policy() -> ConsentPolicyResponse:
        if policy_service is not None:
            policy = policy_service.active()
            if policy is None:
                return ConsentPolicyResponse(version=None, url=None, available=False,
                                             mode=policy_service.mode)
            return ConsentPolicyResponse(id=policy.id, code=policy.code,
                version=policy.version, title=policy.title, content=policy.content,
                effective_at=policy.effective_at, is_demo=policy.is_demo,
                approved=policy.approved, url=None, available=True,
                mode=policy_service.mode)
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

    @router.get("/consent-policies", response_model=list[ConsentPolicyResponse])
    def list_policies(user: User = Depends(current_user)):
        require_superadmin(user)
        if policy_service is None:
            raise HTTPException(503, "Catálogo de políticas no configurado")
        return [ConsentPolicyResponse(id=item.id, code=item.code, version=item.version,
                title=item.title, content=item.content, effective_at=item.effective_at,
                is_demo=item.is_demo, approved=item.approved, url=None,
                available=item.is_active, mode=policy_service.mode)
                for item in policy_service.repository.list_all()]

    @router.post("/consent-policies", response_model=ConsentPolicyResponse, status_code=201)
    def create_policy(request: ConsentPolicyCreate, user: User = Depends(current_user)):
        require_superadmin(user)
        if policy_service is None:
            raise HTTPException(503, "Catálogo de políticas no configurado")
        if request.effective_at.tzinfo is None:
            raise HTTPException(422, "effective_at requiere zona horaria")
        policy_id = f"{request.code.strip()}:{request.version.strip()}"
        try:
            policy = policy_service.repository.save(ConsentPolicy(
                id=policy_id, code=request.code, version=request.version,
                title=request.title, content=request.content,
                effective_at=request.effective_at.astimezone(timezone.utc),
                is_demo=False, approved=request.approved,
            ))
        except (ValueError, IntegrityError) as error:
            raise HTTPException(409, str(error)) from error
        return ConsentPolicyResponse(id=policy.id, code=policy.code, version=policy.version,
            title=policy.title, content=policy.content, effective_at=policy.effective_at,
            is_demo=policy.is_demo, approved=policy.approved, url=None,
            available=False, mode=policy_service.mode)

    @router.post("/consent-policies/{policy_id}/activate", response_model=ConsentPolicyResponse)
    def activate_policy(policy_id: str, user: User = Depends(current_user)):
        require_superadmin(user)
        if policy_service is None:
            raise HTTPException(503, "Catálogo de políticas no configurado")
        try:
            policy_service.activate(policy_id)
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
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
            raise HTTPException(403, "La aceptación la realiza el usuario desde su cuenta")
        student_access(student_id, user, write=True)
        policy = active_policy()
        if not policy.available:
            raise HTTPException(503, "No hay una política de consentimiento activa")
        expected = policy.id or policy.version
        if request.policy_version != expected:
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
