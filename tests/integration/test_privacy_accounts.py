"""Papeles, control de acceso central, compromiso, cifrado, auditoría,
retención y eliminación con acta (SQLite en memoria, sin servicios externos)."""
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
from emotv.application.participant_service import ParticipantService
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
    PostgresParticipantRepository,
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
from emotv.application.stimulus_service import StimulusService
from emotv.infrastructure.persistence.postgres_practice_repositories import (
    PostgresAuthorizationRepository,
    PostgresProtocolRepository,
    PostgresStimulusRepository,
)
from emotv.infrastructure.vision.stimulus_image import sanitize_stimulus_image
from emotv.interfaces.web.stimulus_router import create_stimulus_router
from emotv.infrastructure.persistence.models import (
    AccessAuditRecord,
    ParticipantRecord,
    PsychologistAssignmentRecord,
    SessionRecord,
)
from emotv.interfaces.web.auth_router import create_auth_router
from emotv.interfaces.web.identity_router import create_identity_router
from emotv.interfaces.web.participant_router import create_participant_router
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
    participant_repository = PostgresParticipantRepository(factory, FieldCipher([KEY]))

    def docente_of(user_id):
        student = students.get_by_user_id(user_id)
        assignment = assignments.get_by_student(student.id) if student else None
        return assignment.psychologist_user_id if assignment else None

    def group_user_ids(docente_id):
        return tuple(students.get_by_id(item.student_id).user_id for item in assignments.list_by_psychologist(docente_id))

    authorization = AuthorizationService(assignments.is_assigned, docente_of, participant_repository.get_by_id)
    participants = ParticipantService(participant_repository, authorization, commitments, audit, group_user_ids,
                                      retention_months=12, notice_days=30, clock=clock,
                                      authorizations=PostgresAuthorizationRepository(factory))
    sessions = SessionService(PostgresSessionRepository(factory), consent_repository=consents)
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
    app.include_router(create_participant_router(participants, auth, users))
    app.include_router(create_session_router(sessions, auth, users, students, authorization=authorization,
                                             assignments=assignments, commitments=commitments,
                                             participants=participants, protocols=protocols,
                                             questionnaires=questionnaires))
    app.include_router(create_stimulus_router(stimuli, protocols, auth, users))
    app.include_router(create_questionnaire_router(questionnaires, auth, users))
    app.include_router(create_analysis_router(sessions, ActivityCatalog(), auth, users, students, lambda activity: None,
                                              authorization=authorization,
                                              questionnaire_ready=questionnaires.pre_completed))
    e.audit, e.commitments, e.participants, e.sessions = audit, commitments, participants, sessions
    e.participant_repository, e.authorization = participant_repository, authorization
    e.stimuli, e.protocols, e.questionnaires = stimuli, protocols, questionnaires
    with TestClient(app) as client:
        e.client = client
        yield e
    engine.dispose()


def headers(env, user):
    return {"Authorization": f"Bearer {env.auth.create_access_token(user)}"}


def accept_commitment(env, user):
    env.commitments.accept(user, load_text("commitment").version)


AGES = {"adult": 30, "child": 9}


def register(env, user, kind="adult", notes=None, age=None):
    accept_commitment(env, user)
    if kind == "child":
        env.commitments.accept(user, load_text("child_notice").version, "child_notice")
    response = env.client.post("/participants", headers=headers(env, user),
                               json={"kind": kind, "age_years": age or AGES[kind], "notes": notes})
    assert response.status_code == 201, response.text
    return response.json()


def audit_actions(env, **filters):
    return [(item.action.value, item.resource_type, item.result.value)
            for item in env.audit.query(AuditFilter(**filters), limit=500)]


# --- Acceso a participantes -------------------------------------------------

def test_admin_superadmin_and_a_foreign_user_never_access_a_participant(env):
    participant = register(env, env.user_1)
    for user in (env.admin, env.superadmin, env.user_2, env.docente_b):
        response = env.client.get(f"/participants/{participant['id']}", headers=headers(env, user))
        assert response.status_code == 403, user.role
    for user in (env.admin, env.superadmin):
        assert env.client.get("/participants", headers=headers(env, user)).status_code == 403
    # Quien lo registró y su docente sí acceden.
    for user in (env.user_1, env.docente_a):
        assert env.client.get(f"/participants/{participant['id']}", headers=headers(env, user)).status_code == 200
    denied = [item for item in audit_actions(env, resource_type="participant") if item[2] == "denied"]
    assert len(denied) == 4


def test_a_docente_only_sees_participants_of_their_group_and_their_own(env):
    own = register(env, env.docente_a)
    from_group = register(env, env.user_1)
    other_group = register(env, env.user_2)
    codes = {item["code"] for item in env.client.get("/participants", headers=headers(env, env.docente_a)).json()}
    assert codes == {own["code"], from_group["code"]}
    assert other_group["code"] not in codes
    assert [item["code"] for item in env.client.get("/participants", headers=headers(env, env.user_1)).json()] == [from_group["code"]]


def test_moving_a_user_to_another_docente_moves_access_and_is_audited(env):
    participant = register(env, env.user_1)
    response = env.client.put(f"/users/{env.docente_b.id}/assigned-students/{env.student_1.id}", headers=headers(env, env.admin))
    assert response.status_code == 200
    assert env.client.get(f"/participants/{participant['id']}", headers=headers(env, env.docente_a)).status_code == 403
    assert env.client.get(f"/participants/{participant['id']}", headers=headers(env, env.docente_b)).status_code == 200
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
    accept_commitment(env, env.user_1)
    session = env.client.post("/sessions", headers=headers(env, env.user_1), json={}).json()
    for user in (env.admin, env.superadmin):
        assert env.client.get("/sessions", headers=headers(env, user)).status_code == 403
        assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, user)).status_code == 403
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_a)).status_code == 200
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_b)).status_code == 403


def test_a_docente_opens_and_cancels_their_own_sessions(env):
    accept_commitment(env, env.docente_a)
    response = env.client.post("/sessions", headers=headers(env, env.docente_a), json={})
    assert response.status_code == 201
    session = response.json()
    assert session["owner_user_id"] == env.docente_a.id and session["student_id"] is None
    listed = [item["id"] for item in env.client.get("/sessions", headers=headers(env, env.docente_a)).json()]
    assert session["id"] in listed
    assert env.client.get(f"/sessions/{session['id']}", headers=headers(env, env.docente_b)).status_code == 403
    assert env.client.post(f"/sessions/{session['id']}/cancel", headers=headers(env, env.docente_a)).status_code == 200
    # No inicia sesiones a nombre de un usuario de su grupo.
    assert env.client.post("/sessions", headers=headers(env, env.docente_a),
                           json={"student_id": env.student_1.id}).status_code == 403


# --- Compromiso -------------------------------------------------------------

def test_without_the_commitment_participants_and_sessions_are_refused(env):
    commitment = env.client.get("/commitment", headers=headers(env, env.user_1)).json()
    assert commitment["required"] is True and commitment["provisional"] is True
    assert "no guarda imágenes" in commitment["content"]
    assert env.client.post("/participants", headers=headers(env, env.user_1), json={"kind": "adult", "age_years": 30}).status_code == 428
    assert env.client.post("/sessions", headers=headers(env, env.user_1), json={}).status_code == 428
    accepted = env.client.post("/commitment/accept", headers=headers(env, env.user_1),
                               json={"version": commitment["version"]})
    assert accepted.status_code == 200 and accepted.json()["accepted"] is True
    assert env.client.post("/participants", headers=headers(env, env.user_1), json={"kind": "adult", "age_years": 30}).status_code == 201
    assert ("commitment_accept", "commitment", "success") in audit_actions(env, action="commitment_accept")
    # Una versión distinta no se acepta.
    assert env.client.post("/commitment/accept", headers=headers(env, env.user_2), json={"version": "otra"}).status_code == 409


def test_the_first_child_requires_the_reinforced_notice(env):
    accept_commitment(env, env.user_1)
    assert env.client.post("/participants", headers=headers(env, env.user_1), json={"kind": "child", "age_years": 9}).status_code == 428
    notice = env.client.get("/commitment/child-notice", headers=headers(env, env.user_1)).json()
    assert "más sensibles" in notice["content"]
    created = env.client.post("/participants", headers=headers(env, env.user_1),
                              json={"kind": "child", "age_years": 9, "child_notice_version": notice["version"]})
    assert created.status_code == 201
    # Con el aviso ya aceptado, el siguiente niño no lo vuelve a pedir.
    assert env.client.post("/participants", headers=headers(env, env.user_1), json={"kind": "child", "age_years": 9}).status_code == 201
    assert ("child_notice_accept", "child_notice", "success") in audit_actions(env, action="child_notice_accept")


# --- Cifrado ----------------------------------------------------------------

def test_encrypted_fields_cannot_be_read_from_the_database_without_the_key(env):
    note_text = "Prefiere sesiones por la mañana"
    participant = register(env, env.user_1, notes=note_text)
    with env.engine.connect() as connection:
        stored = connection.execute(text("SELECT notes_encrypted FROM participants WHERE id = :id"),
                                    {"id": participant["id"]}).scalar_one()
    assert note_text not in stored
    with pytest.raises(FieldEncryptionError):
        FieldCipher([Fernet.generate_key().decode()]).decrypt(stored)
    assert FieldCipher([KEY]).decrypt(stored) == note_text
    # Rotación: una clave nueva primero y la anterior después siguen leyendo el dato.
    rotated = FieldCipher([Fernet.generate_key().decode(), KEY])
    assert rotated.decrypt(stored) == note_text and rotated.decrypt(rotated.rotate(stored)) == note_text
    assert env.client.get(f"/participants/{participant['id']}", headers=headers(env, env.user_1)).json()["notes"] == note_text


def test_participant_module_is_unavailable_without_the_key(env):
    app = FastAPI()
    app.include_router(create_participant_router(None, env.auth, env.users))
    with TestClient(app) as client:
        response = client.get("/participants", headers=headers(env, env.user_1))
    assert response.status_code == 503 and "clave de cifrado" in response.json()["detail"]


# --- Auditoría --------------------------------------------------------------

def test_audit_records_accesses_without_content_and_cannot_be_modified(env):
    participant = register(env, env.user_1, notes="texto que nunca va a la auditoría")
    env.client.get(f"/participants/{participant['id']}", headers=headers(env, env.docente_a))
    for user in (env.admin, env.superadmin):
        entries = env.client.get("/audit", headers=headers(env, user), params={"resource_type": "participant"}).json()
        assert {(item["action"], item["actor_role"]) for item in entries} >= {("create", "student"), ("view", "psychologist")}
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
    register(env, env.user_1)
    env.clock.now = NOW + timedelta(days=25 * 30)
    env.audit.record(env.admin, AuditAction.VIEW, "user", "x")
    removed = env.audit.purge_expired(24)
    assert removed >= 1
    assert all(item.occurred_at > NOW for item in env.audit.query(AuditFilter(), limit=500))


# --- Retención y eliminación ------------------------------------------------

def test_retention_deletes_only_expired_participants_with_their_records(env):
    old = register(env, env.user_1)
    env.clock.now = NOW + timedelta(days=200)
    recent = register(env, env.user_1)
    with env.factory.begin() as db:
        for participant, session_id in ((old, "s-old"), (recent, "s-recent")):
            db.add(SessionRecord(id=session_id, state="created", started_at=env.clock.now, session_type="participante_adulto",
                                 participant_id=participant["id"], owner_user_id=env.user_1.id))
    env.clock.now = NOW + timedelta(days=12 * 30 + 1)
    assert env.participants.purge_expired() == 1
    with env.factory() as db:
        assert db.get(ParticipantRecord, old["id"]) is None and db.get(SessionRecord, "s-old") is None
        assert db.get(ParticipantRecord, recent["id"]) is not None and db.get(SessionRecord, "s-recent") is not None
    purge = [item for item in env.audit.query(AuditFilter(action="retention_purge"), limit=10)]
    assert len(purge) == 1 and purge[0].resource_id == "1" and purge[0].actor_user_id is None


def test_the_docente_sees_participants_about_to_expire(env):
    soon = register(env, env.user_1)
    env.clock.now = NOW + timedelta(days=100)
    register(env, env.user_1)
    env.clock.now = NOW + timedelta(days=12 * 30 - 10)
    expiring = env.client.get("/participants/expiring", headers=headers(env, env.docente_a)).json()
    assert [item["code"] for item in expiring] == [soon["code"]]
    assert env.client.get("/participants/expiring", headers=headers(env, env.user_1)).status_code == 403


def test_on_demand_deletion_leaves_zero_records_and_generates_the_certificate(env):
    participant = register(env, env.user_1, notes="nota")
    with env.factory.begin() as db:
        db.add(SessionRecord(id="s-1", state="created", started_at=NOW, session_type="participante_adulto",
                             participant_id=participant["id"], owner_user_id=env.user_1.id))
    # El usuario solo solicita; el docente ejecuta.
    assert env.client.post(f"/participants/{participant['id']}/delete", headers=headers(env, env.user_1)).status_code == 403
    assert env.client.post(f"/participants/{participant['id']}/deletion-request", headers=headers(env, env.user_1)).status_code == 200
    response = env.client.post(f"/participants/{participant['id']}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 200
    certificate = response.json()
    assert certificate["participant_code"] == participant["code"] and certificate["verified"] is True
    assert certificate["counts"] == {"authorizations": 0, "questionnaire_responses": 0, "sessions": 1, "participants": 1}
    with env.factory() as db:
        assert db.scalar(select(func.count()).select_from(ParticipantRecord)) == 0
        assert db.scalar(select(func.count()).select_from(SessionRecord).where(SessionRecord.participant_id == participant["id"])) == 0
    # El acta la ven quien la solicitó y quien la ejecutó; imprimirla queda en la auditoría.
    for user in (env.user_1, env.docente_a):
        assert env.client.get(f"/participant-deletions/{certificate['id']}", headers=headers(env, user)).status_code == 200
    assert env.client.get(f"/participant-deletions/{certificate['id']}", headers=headers(env, env.admin)).status_code == 403
    assert env.client.post(f"/participant-deletions/{certificate['id']}/print", headers=headers(env, env.docente_a)).status_code == 200
    actions = audit_actions(env)
    assert ("deletion_request", "participant", "success") in actions
    assert ("delete", "participant", "success") in actions
    assert ("print", "deletion_certificate", "success") in actions


def test_a_failed_verification_rolls_back_the_whole_deletion(env, monkeypatch):
    participant = register(env, env.user_1)
    monkeypatch.setattr(PostgresParticipantRepository, "remaining",
                        staticmethod(lambda db, participant_id: {"sessions": 1, "participants": 0}))
    with pytest.raises(ErasureVerificationError):
        env.participant_repository.erase(participant["id"])
    with env.factory() as db:
        assert db.get(ParticipantRecord, participant["id"]) is not None
    response = env.client.post(f"/participants/{participant['id']}/delete", headers=headers(env, env.docente_a))
    assert response.status_code == 500
    assert ("delete", "participant", "failure") in audit_actions(env, action="delete")
