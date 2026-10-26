"""Papeles, control de acceso a sesiones, compromiso, cifrado, auditoría,
retención y eliminación por sesión con acta (SQLite en memoria, sin servicios
externos)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application import ActivityCatalog, AuthenticationService, IdentityRegistrationService, SessionService
from emotv.application.audit_service import AuditService
from emotv.application.authorization_service import AuthorizationService
from emotv.application.commitment_service import CommitmentService, load_text
from emotv.application.session_privacy_service import SessionPrivacyService
from emotv.application.ports.privacy_repositories import AuditFilter, ErasureVerificationError
from emotv.config import PrivacySettings
from emotv.domain import AuditAction, Role, User
from emotv.domain.psychologist_assignment import PsychologistAssignment
from emotv.infrastructure.persistence import (
    Base,
    PostgresAssignmentRepository,
    PostgresAuditRepository,
    PostgresCommitmentRepository,
    PostgresConsentRepository,
    PostgresSessionErasureRepository,
    PostgresSessionRepository,
    PostgresStudentRepository,
    PostgresUserRepository,
)
from emotv.application.protocol_service import ProtocolService
from emotv.application.questionnaire_service import QuestionnaireService
from emotv.infrastructure.persistence.postgres_questionnaire_repositories import (
    PostgresQuestionnaireRepository,
    PostgresQuestionnaireResponseRepository,
)
from emotv.interfaces.web.questionnaire_router import create_questionnaire_router
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.application.guided_session_service import GuidedSessionService
from emotv.domain.guided_session import FrameAssessment
from emotv.infrastructure.persistence.postgres_guided_repositories import PostgresGuidedSessionRepository
from emotv.interfaces.web.guided_router import create_guided_router
from emotv.application.session_insights_service import SessionInsightsService
from emotv.interfaces.web.insights_router import create_insights_router
from emotv.application.report_service import ReportService
from emotv.infrastructure.persistence.postgres_report_repository import PostgresReportRepository
from emotv.interfaces.web.report_router import create_report_router
from emotv.application.stimulus_service import StimulusService
from emotv.infrastructure.persistence.postgres_practice_repositories import (
    PostgresProtocolRepository,
    PostgresStimulusRepository,
)
from emotv.infrastructure.vision.stimulus_image import sanitize_stimulus_image
from emotv.interfaces.web.stimulus_router import create_stimulus_router
from emotv.infrastructure.persistence.models import (
    AccessAuditRecord,
    PsychologistAssignmentRecord,
    SessionMarkerRecord,
    SessionRecord,
)
from emotv.interfaces.web.auth_router import create_auth_router
from emotv.interfaces.web.identity_router import create_identity_router
from emotv.interfaces.web.privacy_router import create_privacy_router
from emotv.interfaces.web.session_router import create_session_router
from emotv.shared.security.field_encryption import FieldCipher, FieldEncryptionError

KEY = Fernet.generate_key().decode()
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    users, students = PostgresUserRepository(factory), PostgresStudentRepository(factory)
    consents, assignments = PostgresConsentRepository(factory), PostgresAssignmentRepository(factory)
    auth = AuthenticationService(users, "privacy-tests-secret-at-least-32-characters")
    identity = IdentityRegistrationService(users, students, consents, auth)
    clock = Clock()
    # Cuentas: superadmin, admin, docente A (grupo: usuario 1) y docente B (grupo: usuario 2).
    e = SimpleNamespace(engine=engine, factory=factory, users=users, students=students, assignments=assignments,
                        auth=auth, clock=clock)
    e.superadmin = users.save(User("sa-1", "soporte@example.com", auth.hash_password("superadmin-pass-123"),
                                   Role.SUPERADMIN, NOW))
    e.admin = identity.register_user("facultad@example.com", "admin-password-123", Role.ADMIN)
    e.docente_a = identity.register_user("docente.a@example.com", "docente-a-pass-123", Role.PSYCHOLOGIST)
    e.docente_b = identity.register_user("docente.b@example.com", "docente-b-pass-123", Role.PSYCHOLOGIST)
    e.user_1, e.student_1 = identity.register_student("usuario1@example.com", "usuario-1-pass-123", "U-001")
    e.user_2, e.student_2 = identity.register_student("usuario2@example.com", "usuario-2-pass-123", "U-002")
    for student in (e.student_1, e.student_2):
        identity.grant_consent(student.id, "test-v1")
    assignments.assign(PsychologistAssignment(e.docente_a.id, e.student_1.id, NOW))
    assignments.assign(PsychologistAssignment(e.docente_b.id, e.student_2.id, NOW))

    audit = AuditService(PostgresAuditRepository(factory), clock)
    commitments = CommitmentService(PostgresCommitmentRepository(factory), audit, clock)

    def docente_of(user_id):
        student = students.get_by_user_id(user_id)
        assignment = assignments.get_by_student(student.id) if student else None
        return assignment.psychologist_user_id if assignment else None

    def group_user_ids(docente_id):
        return tuple(students.get_by_id(item.student_id).user_id for item in assignments.list_by_psychologist(docente_id))

    authorization = AuthorizationService(assignments.is_assigned, docente_of)
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents, clock=clock)
    erasure = PostgresSessionErasureRepository(factory)
    privacy = SessionPrivacyService(sessions, erasure, authorization, audit, docente_of, retention_months=12,
                                    clock=clock)
    stimuli = StimulusService(PostgresStimulusRepository(factory), audit, docente_of, sanitize_stimulus_image, clock)
    def session_access(user, session):
        actor = students.get_by_user_id(user.id) if user.role is Role.STUDENT else None
        return authorization.can_access_session(user, session, actor_student_id=actor.id if actor else None)

    questionnaires = QuestionnaireService(
        PostgresQuestionnaireRepository(factory), audit, docente_of,
        responses=PostgresQuestionnaireResponseRepository(factory, FieldCipher([KEY])),
        sessions=sessions.get_session, session_access=session_access, clock=clock)
    protocols = ProtocolService(PostgresProtocolRepository(factory), stimuli, audit, docente_of, group_user_ids,
                                questionnaires=questionnaires, clock=clock)
    app = FastAPI()
    app.include_router(create_auth_router(auth, users))
    app.include_router(create_identity_router(auth, users, students, consents, assignments=assignments, audit=audit,
                                              privacy=PrivacySettings(max_admin_accounts=1)))
    app.include_router(create_privacy_router(commitments, audit, auth, users))
    app.include_router(create_session_router(sessions, auth, users, students, authorization=authorization,
                                             assignments=assignments, commitments=commitments,
                                             protocols=protocols, questionnaires=questionnaires,
                                             privacy=privacy, audit=audit))
    app.include_router(create_stimulus_router(stimuli, protocols, auth, users))
    app.include_router(create_questionnaire_router(questionnaires, auth, users))
    # Analizador falso: cada prueba fija el resultado del próximo cuadro (sin modelos ni imágenes).
    e.frame_result = FrameAssessment((), "happiness", 0.8, {"happiness": 0.8, "neutral": 0.2})
    e.frames_assessed = 0

    def assess(frame):
        e.frames_assessed += 1
        return e.frame_result

    guided = GuidedSessionService(
        PostgresGuidedSessionRepository(factory, FieldCipher([KEY])), sessions,
        protocols=protocols.repository.get, stimuli=stimuli.repository.get,
        questionnaire_answered=questionnaires.answered,
        resolve_model=lambda: ("hsemotion_enet_b0_8_best_afew", "prueba"),
        assess_factory=lambda model_id: assess, audit=audit, session_access=session_access,
        calibration_seconds=3.0, clock=clock)
    app.include_router(create_guided_router(guided, auth, users, stimulus_image=stimuli.repository.get_image,
                                            decode_frame=lambda data: data or None))
    e.guided = guided
    insights = SessionInsightsService(
        sessions, guided.repository, protocols=protocols.repository.get, stimuli=stimuli.repository.get,
        questionnaire_responses=questionnaires.responses.list_for_session,
        questionnaires=questionnaires.repository.get, authorization=authorization,
        actor_student_id=lambda user: (students.get_by_user_id(user.id).id
                                       if user.role is Role.STUDENT and students.get_by_user_id(user.id) else None),
        audit=audit)
    app.include_router(create_insights_router(insights, auth, users))
    e.reports = ReportService(PostgresReportRepository(factory, FieldCipher([KEY])), sessions,
                              authorization, docente_of, insights, audit, clock)
    app.include_router(create_report_router(e.reports, auth, users))
    app.include_router(create_analysis_router(sessions, ActivityCatalog(), auth, users, students, lambda activity: None,
                                              authorization=authorization,
                                              questionnaire_ready=questionnaires.pre_completed))
    e.audit, e.commitments, e.sessions, e.privacy, e.erasure = audit, commitments, sessions, privacy, erasure
    e.authorization = authorization
    e.stimuli, e.protocols, e.questionnaires = stimuli, protocols, questionnaires
    with TestClient(app) as client:
        e.client = client
        yield e
    engine.dispose()


def headers(env, user):
    return {"Authorization": f"Bearer {env.auth.create_access_token(user)}"}


def accept_commitment(env, user):
    env.commitments.accept(user, load_text("commitment").version)


CONFIRMED = {"authorization_confirmed": True}


def start_session(env, user, session_type="adulto", **body):
    """Inicia una sesión sin protocolo con la confirmación según el público."""
    accept_commitment(env, user)
    if session_type == "infantil":
        env.commitments.accept(user, load_text("child_notice").version, "child_notice")
    response = env.client.post("/sessions", headers=headers(env, user),
                               json={"session_type": session_type, **CONFIRMED, **body})
    assert response.status_code == 201, response.text
    return response.json()


def finish(env, user, session):
    """Deja la sesión terminada (cancelada) para poder eliminarla."""
    assert env.client.post(f"/sessions/{session['id']}/cancel", headers=headers(env, user)).status_code == 200


def audit_actions(env, **filters):
    return [(item.action.value, item.resource_type, item.result.value)
            for item in env.audit.query(AuditFilter(**filters), limit=500)]


# --- Acceso a sesiones (can_access_session) -----------------------------------

def test_only_the_conductor_and_their_docente_access_a_session(env):
    session = start_session(env, env.user_1)
    for user in (env.admin, env.superadmin, env.user_2, env.docente_b):
        response = env.client.get(f"/sessions/{session['id']}", headers=headers(env, user))
        assert response.status_code == 403, user.role
    for user in (env.admin, env.superadmin):
        assert env.client.get("/sessions", headers=headers(env, user)).status_code == 403
    for user in (env.user_1, env.docente_a):
        assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, user)).status_code == 200


def test_a_docente_only_sees_sessions_of_their_group_and_their_own(env):
    own = start_session(env, env.docente_a, "propia")
    from_group = start_session(env, env.user_1)
    other_group = start_session(env, env.user_2)
    codes = {item["code"] for item in env.client.get("/sessions", headers=headers(env, env.docente_a)).json()}
    assert codes == {own["code"], from_group["code"]}
    assert other_group["code"] not in codes
    assert [item["code"] for item in env.client.get("/sessions", headers=headers(env, env.user_1)).json()] == [
        from_group["code"]]


def test_moving_a_user_to_another_docente_moves_access_and_is_audited(env):
    session = start_session(env, env.user_1)
    response = env.client.put(f"/users/{env.docente_b.id}/assigned-students/{env.student_1.id}", headers=headers(env, env.admin))
    assert response.status_code == 200
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_a)).status_code == 403
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_b)).status_code == 200
    assert ("group_change", "student", "success") in audit_actions(env, action="group_change")
    # Solo el administrador mueve usuarios entre grupos.
    for user in (env.superadmin, env.docente_a):
        assert env.client.put(f"/users/{env.docente_a.id}/assigned-students/{env.student_1.id}",
                              headers=headers(env, user)).status_code == 403


def test_a_user_cannot_have_two_docentes(env):
    env.assignments.assign(PsychologistAssignment(env.docente_b.id, env.student_1.id, NOW + timedelta(minutes=1)))
    assert env.assignments.get_by_student(env.student_1.id).psychologist_user_id == env.docente_b.id
    assert not env.assignments.is_assigned(env.docente_a.id, env.student_1.id)
    with pytest.raises(IntegrityError):  # la base de datos también lo impide
        with env.factory.begin() as db:
            db.add(PsychologistAssignmentRecord(psychologist_user_id=env.docente_a.id, student_id=env.student_1.id,
                                                assigned_at=NOW))


# --- Cuentas ----------------------------------------------------------------

def test_only_the_superadmin_creates_the_admin_account_and_the_maximum_holds(env):
    body = {"email": "otra.facultad@example.com", "role": "admin"}
    assert env.client.post("/users", headers=headers(env, env.admin), json=body).status_code == 403
    assert env.client.post("/users", headers=headers(env, env.docente_a), json=body).status_code == 403
    # Ya hay un administrador activo: el máximo (1) impide crear otro.
    assert env.client.post("/users", headers=headers(env, env.superadmin), json=body).status_code == 409
    assert env.client.patch(f"/users/{env.admin.id}", headers=headers(env, env.superadmin),
                            json={"is_active": False}).status_code == 200
    created = env.client.post("/users", headers=headers(env, env.superadmin), json=body)
    assert created.status_code == 201 and created.json()["temporary_password"]
    # Reactivar el anterior superaría el máximo.
    assert env.client.patch(f"/users/{env.admin.id}", headers=headers(env, env.superadmin),
                            json={"is_active": True}).status_code == 409
    # El superadministrador no gestiona docentes ni usuarios, y el administrador sí.
    assert env.client.post("/users", headers=headers(env, env.superadmin),
                           json={"email": "d@example.com", "role": "psychologist"}).status_code == 403
    new_admin = env.users.save(replace(env.users.get_by_email("otra.facultad@example.com"), must_change_password=False))
    assert env.client.post("/users", headers=headers(env, new_admin),
                           json={"email": "d@example.com", "role": "psychologist"}).status_code == 201
    assert ("account_create", "user", "success") in audit_actions(env, action="account_create")


def test_password_reset_shows_a_notice_and_is_audited(env):
    response = env.client.post(f"/users/{env.user_1.id}/reset-password", headers=headers(env, env.admin))
    assert response.status_code == 200
    temporary = response.json()["temporary_password"]
    assert temporary
    reset_user = env.users.get_by_id(env.user_1.id)
    assert reset_user.must_change_password and reset_user.password_reset_at is not None
    me = env.client.get("/auth/me", headers=headers(env, reset_user)).json()
    assert me["password_reset"] is True and me["must_change_password"] is True
    assert ("password_reset", "user", "success") in audit_actions(env, action="password_reset")
    token = env.client.post("/auth/change-password", headers=headers(env, reset_user),
                            json={"current_password": temporary, "new_password": "una-clave-nueva-larga-2026"})
    assert token.status_code == 200
    assert env.users.get_by_id(env.user_1.id).password_reset_at is None
    # El superadministrador restablece solo al administrador.
    assert env.client.post(f"/users/{env.user_2.id}/reset-password", headers=headers(env, env.superadmin)).status_code == 404
    assert env.client.post(f"/users/{env.admin.id}/reset-password", headers=headers(env, env.superadmin)).status_code == 200


def test_management_roles_never_reach_sessions(env):
    session = start_session(env, env.user_1)
    for user in (env.admin, env.superadmin):
        assert env.client.get("/sessions", headers=headers(env, user)).status_code == 403
        assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, user)).status_code == 403
        assert env.client.get("/session-deletions", headers=headers(env, user)).status_code == 403
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_a)).status_code == 200
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_b)).status_code == 403


def test_a_docente_opens_and_cancels_their_own_sessions(env):
    session = start_session(env, env.docente_a, "propia")
    assert session["owner_user_id"] == env.docente_a.id and session["student_id"] is None
    listed = [item["id"] for item in env.client.get("/sessions", headers=headers(env, env.docente_a)).json()]
    assert session["id"] in listed
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_b)).status_code == 403
    assert env.client.post(f"/sessions/{session['id']}/cancel", headers=headers(env, env.docente_a)).status_code == 200
    # No inicia sesiones a nombre de un usuario de su grupo.
    assert env.client.post("/sessions", headers=headers(env, env.docente_a),
                           json={"student_id": env.student_1.id, "session_type": "propia",
                                 **CONFIRMED}).status_code == 403


# --- Inicio: sin protocolo, público y una sola confirmación ---------------------

def test_starting_without_a_protocol_needs_nothing_created_first(env):
    accept_commitment(env, env.user_1)
    response = env.client.post("/sessions", headers=headers(env, env.user_1),
                               json={"session_type": "propia", **CONFIRMED})
    assert response.status_code == 201, response.text
    session = response.json()
    assert session["protocol_id"] is None and session["session_type"] == "propia"
    assert session["authorization_confirmed_at"] is not None
    assert ("create", "session", "success") in audit_actions(env, resource_type="session")


def test_without_a_protocol_the_audience_is_required(env):
    accept_commitment(env, env.user_1)
    response = env.client.post("/sessions", headers=headers(env, env.user_1), json=CONFIRMED)
    assert response.status_code == 422 and "con quién" in response.json()["detail"]


def test_no_session_starts_without_the_confirmation(env):
    accept_commitment(env, env.user_1)
    env.commitments.accept(env.user_1, load_text("child_notice").version, "child_notice")
    for session_type in ("propia", "adulto", "infantil"):
        response = env.client.post("/sessions", headers=headers(env, env.user_1), json={"session_type": session_type})
        assert response.status_code == 422, session_type
        response = env.client.post("/sessions", headers=headers(env, env.user_1),
                                   json={"session_type": session_type, "authorization_confirmed": False})
        assert response.status_code == 422, session_type
    adult = env.client.post("/sessions", headers=headers(env, env.user_1), json={"session_type": "adulto"})
    assert "autorización firmada de la persona adulta" in adult.json()["detail"]
    child = env.client.post("/sessions", headers=headers(env, env.user_1), json={"session_type": "infantil"})
    assert "tutor autorizó por escrito" in child.json()["detail"]
    assert not env.sessions.list_sessions_by_owner(env.user_1.id)


def test_without_a_protocol_questionnaires_and_participants_are_not_accepted(env):
    accept_commitment(env, env.user_1)
    for field in ("pre_questionnaire_id", "post_questionnaire_id", "participant_id"):
        response = env.client.post("/sessions", headers=headers(env, env.user_1),
                                   json={"session_type": "adulto", **CONFIRMED, field: "x"})
        assert response.status_code == 422, field


def test_the_session_code_is_random_and_unique(env):
    codes = {start_session(env, env.user_1)["code"] for _ in range(5)}
    assert len(codes) == 5
    assert all(code.startswith("S-") and len(code) == 8 for code in codes)


# --- Compromiso -------------------------------------------------------------

def test_without_the_commitment_sessions_are_refused(env):
    commitment = env.client.get("/commitment", headers=headers(env, env.user_1)).json()
    assert commitment["required"] is True and commitment["provisional"] is True
    assert "no guarda imágenes" in commitment["content"]
    body = {"session_type": "adulto", **CONFIRMED}
    assert env.client.post("/sessions", headers=headers(env, env.user_1), json=body).status_code == 428
    accepted = env.client.post("/commitment/accept", headers=headers(env, env.user_1),
                               json={"version": commitment["version"]})
    assert accepted.status_code == 200 and accepted.json()["accepted"] is True
    assert env.client.post("/sessions", headers=headers(env, env.user_1), json=body).status_code == 201
    assert ("commitment_accept", "commitment", "success") in audit_actions(env, action="commitment_accept")
    # Una versión distinta no se acepta.
    assert env.client.post("/commitment/accept", headers=headers(env, env.user_2), json={"version": "otra"}).status_code == 409


def test_the_first_session_with_a_child_requires_the_reinforced_notice(env):
    accept_commitment(env, env.user_1)
    body = {"session_type": "infantil", **CONFIRMED}
    missing = env.client.post("/sessions", headers=headers(env, env.user_1), json=body)
    assert missing.status_code == 428 and missing.headers["X-EMOtv-Required"] == "child_notice"
    notice = env.client.get("/commitment/child-notice", headers=headers(env, env.user_1)).json()
    assert "más sensibles" in notice["content"]
    created = env.client.post("/sessions", headers=headers(env, env.user_1),
                              json={**body, "child_notice_version": notice["version"]})
    assert created.status_code == 201 and created.json()["session_type"] == "infantil"
    # Con el aviso ya aceptado, la siguiente sesión con un niño no lo vuelve a pedir.
    assert env.client.post("/sessions", headers=headers(env, env.user_1), json=body).status_code == 201
    assert ("child_notice_accept", "child_notice", "success") in audit_actions(env, action="child_notice_accept")


# --- Cifrado ----------------------------------------------------------------

def test_encrypted_fields_cannot_be_read_from_the_database_without_the_key(env):
    note_text = "Se distrajo con un ruido de la calle"
    session = start_session(env, env.user_1)
    assert env.client.post(f"/guided-sessions/{session['id']}", headers=headers(env, env.user_1)).status_code == 201
    marker = env.client.post(f"/guided-sessions/{session['id']}/markers", headers=headers(env, env.user_1),
                             json={"kind": "note", "note": note_text})
    assert marker.status_code == 201, marker.text
    with env.engine.connect() as connection:
        stored = connection.execute(text("SELECT note_encrypted FROM session_markers WHERE session_id = :id"),
                                    {"id": session["id"]}).scalar_one()
    assert note_text not in stored
    with pytest.raises(FieldEncryptionError):
        FieldCipher([Fernet.generate_key().decode()]).decrypt(stored)
    assert FieldCipher([KEY]).decrypt(stored) == note_text
    # Rotación: una clave nueva primero y la anterior después siguen leyendo el dato.
    rotated = FieldCipher([Fernet.generate_key().decode(), KEY])
    assert rotated.decrypt(stored) == note_text and rotated.decrypt(rotated.rotate(stored)) == note_text


def test_sessions_with_a_protocol_are_unavailable_without_the_key(env):
    app = FastAPI()
    app.include_router(create_guided_router(None, env.auth, env.users))
    with TestClient(app) as client:
        response = client.post("/guided-sessions/s-1", headers=headers(env, env.user_1))
    assert response.status_code == 503 and "clave de cifrado" in response.json()["detail"]


# --- Auditoría --------------------------------------------------------------

def test_audit_records_accesses_without_content_and_cannot_be_modified(env):
    session = start_session(env, env.user_1)
    env.client.post(f"/guided-sessions/{session['id']}", headers=headers(env, env.user_1))
    env.client.post(f"/guided-sessions/{session['id']}/markers", headers=headers(env, env.user_1),
                    json={"kind": "note", "note": "texto que nunca va a la auditoría"})
    env.client.get(f"/sessions/{session['id']}/guided-results", headers=headers(env, env.docente_a))
    for user in (env.admin, env.superadmin):
        entries = env.client.get("/audit", headers=headers(env, user), params={"resource_type": "session"}).json()
        assert ("create", "student") in {(item["action"], item["actor_role"]) for item in entries}
    for user in (env.user_1, env.docente_a):
        assert env.client.get("/audit", headers=headers(env, user)).status_code == 403
    entry_id = entries[0]["id"]
    for method in ("post", "put", "patch", "delete"):
        assert getattr(env.client, method)("/audit", headers=headers(env, env.admin)).status_code == 405
        assert getattr(env.client, method)(f"/audit/{entry_id}", headers=headers(env, env.admin)).status_code in (404, 405)
    with env.factory() as db:
        rows = db.scalars(select(AccessAuditRecord)).all()
    dumped = " ".join(f"{row.action} {row.resource_type} {row.resource_id} {row.actor_role}" for row in rows)
    assert "texto que nunca" not in dumped


def test_audit_retention_removes_only_old_entries(env):
    start_session(env, env.user_1)
    env.clock.now = NOW + timedelta(days=25 * 30)
    env.audit.record(env.admin, AuditAction.VIEW, "user", "x")
    removed = env.audit.purge_expired(24)
    assert removed >= 1
    assert all(item.occurred_at > NOW for item in env.audit.query(AuditFilter(), limit=500))


# --- Retención y eliminación por sesión ---------------------------------------

def add_marker_row(env, session_id):
    with env.factory.begin() as db:
        db.add(SessionMarkerRecord(id=f"m-{session_id}", session_id=session_id, kind="laughed",
                                   occurred_at=env.clock.now, recorded_by_user_id=env.user_1.id))


def test_retention_deletes_only_expired_sessions_with_their_records(env):
    old = start_session(env, env.user_1)
    add_marker_row(env, old["id"])
    env.clock.now = NOW + timedelta(days=200)
    recent = start_session(env, env.user_1)
    add_marker_row(env, recent["id"])
    env.clock.now = NOW + timedelta(days=12 * 30 + 1)
    assert env.privacy.purge_expired() == 1
    with env.factory() as db:
        assert db.get(SessionRecord, old["id"]) is None and db.get(SessionMarkerRecord, f"m-{old['id']}") is None
        assert db.get(SessionRecord, recent["id"]) is not None
        assert db.get(SessionMarkerRecord, f"m-{recent['id']}") is not None
    purge = [item for item in env.audit.query(AuditFilter(action="retention_purge"), limit=10)]
    assert len(purge) == 1 and purge[0].resource_id == "1" and purge[0].actor_user_id is None


def test_deleting_a_session_leaves_zero_records_and_produces_the_certificate(env):
    session = start_session(env, env.user_1)
    add_marker_row(env, session["id"])
    # Una sesión en curso no se elimina.
    assert env.client.post(f"/sessions/{session['id']}/delete", headers=headers(env, env.docente_a)).status_code == 409
    finish(env, env.user_1, session)
    # El usuario solo solicita; el docente ejecuta. Nadie más hace ninguna de las dos cosas.
    assert env.client.post(f"/sessions/{session['id']}/delete", headers=headers(env, env.user_1)).status_code == 403
    for user in (env.docente_a, env.docente_b, env.admin):
        assert env.client.post(f"/sessions/{session['id']}/deletion-request",
                               headers=headers(env, user)).status_code == 403, user.role
    for user in (env.docente_b, env.admin, env.superadmin):
        assert env.client.post(f"/sessions/{session['id']}/delete", headers=headers(env, user)).status_code == 403
    requested = env.client.post(f"/sessions/{session['id']}/deletion-request", headers=headers(env, env.user_1))
    assert requested.status_code == 200 and requested.json()["deletion_requested_at"]
    response = env.client.post(f"/sessions/{session['id']}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 200
    certificate = response.json()
    assert certificate["session_code"] == session["code"] and certificate["verified"] is True
    assert certificate["counts"] == {"questionnaire_responses": 0, "expression_captures": 0, "session_markers": 1,
                                     "verbal_responses": 0, "guided_runs": 0, "report_comments": 0,
                                     "report_events": 0, "session_reports": 0, "sessions": 1}
    assert not set(certificate) & {"owner_user_id", "student_id", "executed_by_user_id", "requested_by_user_id"}
    with env.factory() as db:
        assert all(value == 0 for value in env.erasure.remaining(db, session["id"]).values())
    # El acta la ven quien la solicitó y quien la ejecutó; imprimirla queda en la auditoría.
    for user in (env.user_1, env.docente_a):
        assert env.client.get(f"/session-deletions/{certificate['id']}", headers=headers(env, user)).status_code == 200
        listed = env.client.get("/session-deletions", headers=headers(env, user)).json()
        assert [item["session_code"] for item in listed] == [session["code"]]
    for user in (env.admin, env.docente_b, env.user_2):
        assert env.client.get(f"/session-deletions/{certificate['id']}",
                              headers=headers(env, user)).status_code == 403
    assert env.client.post(f"/session-deletions/{certificate['id']}/print",
                           headers=headers(env, env.docente_a)).status_code == 200
    actions = audit_actions(env)
    assert ("deletion_request", "session", "success") in actions
    assert ("delete", "session", "success") in actions
    assert ("print", "deletion_certificate", "success") in actions


def test_a_docente_deletes_their_own_session_directly(env):
    session = start_session(env, env.docente_a, "propia")
    finish(env, env.docente_a, session)
    response = env.client.post(f"/sessions/{session['id']}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 200 and response.json()["counts"]["sessions"] == 1
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_a)).status_code == 404


def test_a_failed_verification_rolls_back_the_whole_deletion(env, monkeypatch):
    session = start_session(env, env.user_1)
    finish(env, env.user_1, session)
    monkeypatch.setattr(PostgresSessionErasureRepository, "remaining",
                        staticmethod(lambda db, session_id: {"sessions": 1}))
    with pytest.raises(ErasureVerificationError):
        env.erasure.erase(session["id"])
    with env.factory() as db:
        assert db.get(SessionRecord, session["id"]) is not None
    response = env.client.post(f"/sessions/{session['id']}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 500
    assert ("delete", "session", "failure") in audit_actions(env, action="delete")
    with env.factory() as db:
        assert db.get(SessionRecord, session["id"]) is not None
