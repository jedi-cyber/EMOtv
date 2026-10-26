from __future__ import annotations

import unittest
from datetime import datetime, timezone

from emotv.application import AuthorizationService
from emotv.domain import AccessAction, EmotionalSession, Role, User

SESSION_SCOPED = (AccessAction.START_SESSION, AccessAction.CANCEL_SESSION, AccessAction.VIEW_SESSION,
                  AccessAction.LIST_STUDENT_SESSIONS)


class AuthorizationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AuthorizationService()
        now = datetime.now(timezone.utc)
        self.student = User("user-s", "s@example.com", "hash", Role.STUDENT, now)
        self.psychologist = User("user-p", "p@example.com", "hash", Role.PSYCHOLOGIST, now)
        self.admin = User("user-a", "a@example.com", "hash", Role.ADMIN, now)
        self.superadmin = User("user-sa", "sa@example.com", "hash", Role.SUPERADMIN, now)
        self.now = now

    def test_management_roles_never_reach_sessions(self) -> None:
        for user in (self.admin, self.superadmin):
            for action in SESSION_SCOPED:
                with self.subTest(role=user.role, action=action):
                    self.assertFalse(self.service.is_allowed(user, action, resource_student_id="student-1"))

    def test_management_roles_split_accounts_and_technical_configuration(self) -> None:
        self.assertTrue(self.service.is_allowed(self.admin, AccessAction.MANAGE_USERS))
        self.assertTrue(self.service.is_allowed(self.admin, AccessAction.VIEW_AUDIT))
        self.assertFalse(self.service.is_allowed(self.admin, AccessAction.MANAGE_ACTIVITIES))
        self.assertFalse(self.service.is_allowed(self.admin, AccessAction.MANAGE_TECHNICAL))
        self.assertTrue(self.service.is_allowed(self.superadmin, AccessAction.MANAGE_ACTIVITIES))
        self.assertTrue(self.service.is_allowed(self.superadmin, AccessAction.MANAGE_ADMIN_ACCOUNT))
        self.assertTrue(self.service.is_allowed(self.superadmin, AccessAction.VIEW_AUDIT))
        self.assertFalse(self.service.is_allowed(self.superadmin, AccessAction.MANAGE_STUDENTS))

    def test_psychologist_only_follows_assigned_students(self) -> None:
        service = AuthorizationService(lambda psychologist, student: (psychologist, student) == ("user-p", "student-1"))
        for action in (AccessAction.VIEW_SESSION, AccessAction.LIST_STUDENT_SESSIONS):
            with self.subTest(action=action):
                self.assertTrue(service.is_allowed(self.psychologist, action, resource_student_id="student-1"))
                self.assertFalse(service.is_allowed(self.psychologist, action, resource_student_id="student-2"))
                self.assertFalse(service.is_allowed(self.psychologist, action))

    def test_psychologist_is_denied_without_assignment_lookup(self) -> None:
        self.assertFalse(self.service.is_allowed(
            self.psychologist, AccessAction.VIEW_SESSION, resource_student_id="student-1",
        ))

    def test_psychologist_starts_own_sessions_but_not_for_a_user(self) -> None:
        service = AuthorizationService(lambda psychologist, student: True)
        self.assertTrue(service.is_allowed(self.psychologist, AccessAction.START_SESSION))
        self.assertTrue(service.is_allowed(self.psychologist, AccessAction.START_SESSION, resource_student_id="student-1"))
        self.assertFalse(service.is_allowed(self.psychologist, AccessAction.CANCEL_SESSION))

    def test_can_access_session_follows_the_conductor_and_their_current_docente(self) -> None:
        docentes = {"user-s": "user-p"}
        service = AuthorizationService(docente_of=docentes.get)
        session = EmotionalSession(id="s-1", started_at=self.now, session_type="adulto", owner_user_id="user-s")
        other_student = User("user-s2", "s2@example.com", "hash", Role.STUDENT, self.now)
        other_docente = User("user-p2", "p2@example.com", "hash", Role.PSYCHOLOGIST, self.now)
        self.assertTrue(service.can_access_session(self.student, session))
        self.assertTrue(service.can_access_session(self.psychologist, session))
        for user in (other_student, other_docente, self.admin, self.superadmin):
            with self.subTest(user=user.id):
                self.assertFalse(service.can_access_session(user, session))
        # Al cambiar de docente, el acceso sigue la asignación vigente.
        docentes["user-s"] = "user-p2"
        self.assertFalse(service.can_access_session(self.psychologist, session))
        self.assertTrue(service.can_access_session(other_docente, session))
        # El docente accede a las sesiones que condujo él mismo; nadie más que su docente.
        own = EmotionalSession(id="s-2", started_at=self.now, owner_user_id="user-p")
        self.assertTrue(service.can_access_session(self.psychologist, own))
        self.assertFalse(service.can_access_session(self.student, own))
        self.assertFalse(service.can_access_session(self.student, None))

    def test_inactive_accounts_never_access_a_session(self) -> None:
        service = AuthorizationService(docente_of={"user-s": "user-p"}.get)
        session = EmotionalSession(id="s-1", started_at=self.now, owner_user_id="user-s")
        inactive = User(self.psychologist.id, self.psychologist.email, "hash", Role.PSYCHOLOGIST, self.now,
                        is_active=False)
        self.assertFalse(service.can_access_session(inactive, session))

    def test_psychologist_cannot_manage_users_or_consent(self) -> None:
        self.assertFalse(self.service.is_allowed(
            self.psychologist, AccessAction.MANAGE_USERS,
        ))
        self.assertFalse(self.service.is_allowed(
            self.psychologist, AccessAction.MANAGE_CONSENT,
        ))

    def test_student_can_only_access_own_resources(self) -> None:
        self.assertTrue(self.service.is_allowed(
            self.student, AccessAction.START_SESSION,
            actor_student_id="student-1", resource_student_id="student-1",
        ))
        self.assertFalse(self.service.is_allowed(
            self.student, AccessAction.START_SESSION,
            actor_student_id="student-1", resource_student_id="student-2",
        ))
        self.assertFalse(self.service.is_allowed(
            self.student, AccessAction.VIEW_SESSION,
            actor_student_id="student-1",
        ))

    def test_student_cannot_administer_system(self) -> None:
        for action in (
            AccessAction.REGISTER_USER,
            AccessAction.MANAGE_USERS,
            AccessAction.MANAGE_STUDENTS,
            AccessAction.MANAGE_ACTIVITIES,
        ):
            self.assertFalse(self.service.is_allowed(self.student, action))

    def test_inactive_user_is_always_denied(self) -> None:
        inactive = User(
            self.admin.id, self.admin.email, self.admin.password_hash,
            self.admin.role, self.admin.created_at, is_active=False,
        )
        self.assertFalse(self.service.is_allowed(inactive, AccessAction.MANAGE_USERS))

    def test_require_raises_permission_error(self) -> None:
        with self.assertRaises(PermissionError):
            self.service.require(self.student, AccessAction.MANAGE_USERS)


if __name__ == "__main__":
    unittest.main()
