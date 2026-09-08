from __future__ import annotations

import unittest
from datetime import datetime, timezone

from emotv.application import AuthorizationService
from emotv.domain import AccessAction, Role, User


class AuthorizationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AuthorizationService()
        now = datetime.now(timezone.utc)
        self.student = User("user-s", "s@example.com", "hash", Role.STUDENT, now)
        self.psychologist = User("user-p", "p@example.com", "hash", Role.PSYCHOLOGIST, now)
        self.admin = User("user-a", "a@example.com", "hash", Role.ADMIN, now)

    def test_admin_can_perform_every_action(self) -> None:
        for action in AccessAction:
            with self.subTest(action=action):
                self.assertTrue(self.service.is_allowed(self.admin, action))

    def test_psychologist_can_follow_students_but_not_manage_users(self) -> None:
        self.assertTrue(self.service.is_allowed(
            self.psychologist, AccessAction.VIEW_SESSION,
            resource_student_id="student-1",
        ))
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
