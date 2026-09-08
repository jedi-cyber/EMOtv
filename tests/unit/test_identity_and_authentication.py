from __future__ import annotations

import unittest
from datetime import datetime, timezone

from emotv.application import AuthenticationService
from emotv.domain import ConsentRecord, Role, Student, User


class UserStore:
    def __init__(self) -> None:
        self.user: User | None = None

    def get_by_email(self, email: str) -> User | None:
        return self.user if self.user and self.user.email == email else None


class IdentityAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(timezone.utc)
        self.store = UserStore()
        self.auth = AuthenticationService(
            self.store,
            "test-secret-key-with-at-least-32-characters",
            clock=lambda: self.now,
        )

    def test_hashes_authenticates_and_issues_role_token(self) -> None:
        password_hash = self.auth.hash_password("correct-password-123")
        self.assertNotIn("correct-password-123", password_hash)
        self.store.user = User(
            "user-1", "Student@Example.com", password_hash,
            Role.STUDENT, self.now,
        )

        user = self.auth.authenticate("student@example.com", "correct-password-123")
        self.assertEqual(user, self.store.user)
        claims = self.auth.decode_access_token(self.auth.create_access_token(user))
        self.assertEqual(claims["sub"], "user-1")
        self.assertEqual(claims["role"], "student")

    def test_rejects_wrong_password_and_inactive_user(self) -> None:
        self.store.user = User(
            "user-1", "student@example.com",
            self.auth.hash_password("correct-password-123"),
            Role.STUDENT, self.now, is_active=False,
        )
        self.assertIsNone(self.auth.authenticate("student@example.com", "wrong"))

    def test_student_and_versioned_consent(self) -> None:
        student = Student("student-1", "user-1", "2026-001")
        consent = ConsentRecord("consent-1", student.id, "privacy-v1", self.now)
        self.assertTrue(consent.is_active)


if __name__ == "__main__":
    unittest.main()
