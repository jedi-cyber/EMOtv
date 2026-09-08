from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from emotv.application import AuthenticationService, SessionService
from emotv.config import get_database_url
from emotv.domain import ConsentRecord, Role, Student, User
from emotv.infrastructure.persistence import (
    PostgresUserRepository,
    PostgresStudentRepository,
    PostgresConsentRepository,
    PostgresSessionRepository,
    create_database_engine,
)
from emotv.interfaces.web.auth_router import create_auth_router
from emotv.interfaces.web.session_router import create_session_router


@pytest.mark.integration
class AuthenticationApiIntegrationTests(unittest.TestCase):
    engine: Engine

    @classmethod
    def setUpClass(cls) -> None:
        try:
            database_url = get_database_url()
        except RuntimeError as error:
            raise unittest.SkipTest(str(error)) from error
        cls.engine = create_database_engine(database_url)
        with cls.engine.connect() as connection:
            if "users" not in inspect(connection).get_table_names():
                cls.engine.dispose()
                raise RuntimeError(
                    "Falta la tabla users. Ejecuta: python -m alembic upgrade head"
                )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def setUp(self) -> None:
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        factory = sessionmaker(
            bind=self.connection,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.users = PostgresUserRepository(factory)
        self.students = PostgresStudentRepository(factory)
        self.consents = PostgresConsentRepository(factory)
        self.sessions = SessionService(
            PostgresSessionRepository(factory),
            consent_repository=self.consents,
        )
        self.authentication = AuthenticationService(
            self.users,
            "integration-jwt-secret-with-at-least-32-characters",
        )
        suffix = str(uuid4())
        now = datetime.now(timezone.utc)
        self.student_password = "student-integration-password"
        self.admin_password = "administrator-integration-password"
        self.student = User(
            id=f"student-user-{suffix}",
            email=f"student-{suffix}@example.com",
            password_hash=self.authentication.hash_password(self.student_password),
            role=Role.STUDENT,
            created_at=now,
        )
        self.admin = User(
            id=f"admin-user-{suffix}",
            email=f"admin-{suffix}@example.com",
            password_hash=self.authentication.hash_password(self.admin_password),
            role=Role.ADMIN,
            created_at=now,
        )
        self.users.save(self.student)
        self.users.save(self.admin)
        self.student_profile = Student(
            id=f"student-profile-{suffix}",
            user_id=self.student.id,
            student_code=f"student-code-{suffix}",
        )
        self.students.save(self.student_profile)
        self.consents.save(ConsentRecord(
            id=f"consent-{suffix}",
            student_id=self.student_profile.id,
            policy_version="privacy-v1",
            granted_at=now,
        ))
        app = FastAPI()
        app.include_router(create_auth_router(self.authentication, self.users))
        app.include_router(create_session_router(
            self.sessions,
            self.authentication,
            self.users,
            self.students,
        ))
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        if self.transaction.is_active:
            self.transaction.rollback()
        self.connection.close()

    def _login(self, email: str, password: str) -> str:
        response = self.client.post(
            "/auth/token",
            data={"username": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_login_and_me_use_user_persisted_in_postgres(self) -> None:
        token = self._login(self.student.email, self.student_password)

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.student.id)
        self.assertEqual(response.json()["role"], "student")
        self.assertNotIn("password_hash", response.json())

    def test_database_role_controls_protected_endpoint(self) -> None:
        student_token = self._login(self.student.email, self.student_password)
        admin_token = self._login(self.admin.email, self.admin_password)

        denied = self.client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        allowed = self.client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertIn(self.admin.id, {item["id"] for item in allowed.json()})

    def test_wrong_password_and_invalid_token_are_rejected(self) -> None:
        login = self.client.post(
            "/auth/token",
            data={"username": self.student.email, "password": "wrong-password"},
        )
        protected = self.client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        self.assertEqual(login.status_code, 401)
        self.assertEqual(protected.status_code, 401)
        self.assertEqual(protected.headers["www-authenticate"], "Bearer")

    def test_student_creates_and_cancels_own_consented_session(self) -> None:
        token = self._login(self.student.email, self.student_password)
        headers = {"Authorization": f"Bearer {token}"}

        created = self.client.post("/sessions", json={}, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["state"], "in_progress")
        self.assertEqual(created.json()["student_id"], self.student_profile.id)

        cancelled = self.client.post(
            f"/sessions/{created.json()['id']}/cancel",
            headers=headers,
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["state"], "cancelled")
        self.assertIsNotNone(cancelled.json()["completed_at"])

    def test_student_cannot_create_session_for_another_student(self) -> None:
        token = self._login(self.student.email, self.student_password)
        response = self.client.post(
            "/sessions",
            json={"student_id": "another-student"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)

    def test_student_gets_session_by_id_and_lists_only_own_sessions(self) -> None:
        token = self._login(self.student.email, self.student_password)
        headers = {"Authorization": f"Bearer {token}"}
        created = self.client.post("/sessions", json={}, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        session_id = created.json()["id"]

        detail = self.client.get(f"/sessions/{session_id}", headers=headers)
        listing = self.client.get("/sessions", headers=headers)

        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["id"], session_id)
        self.assertIn(session_id, {item["id"] for item in listing.json()})
        self.assertTrue(all(
            item["student_id"] == self.student_profile.id
            for item in listing.json()
        ))

    def test_student_cannot_get_or_list_another_students_sessions(self) -> None:
        token = self._login(self.student.email, self.student_password)
        admin_token = self._login(self.admin.email, self.admin_password)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created = self.client.post(
            "/sessions",
            json={"student_id": None},
            headers=admin_headers,
        )
        self.assertEqual(created.status_code, 201, created.text)
        student_headers = {"Authorization": f"Bearer {token}"}

        detail = self.client.get(
            f"/sessions/{created.json()['id']}", headers=student_headers
        )
        listing = self.client.get(
            "/sessions?student_id=another-student", headers=student_headers
        )

        self.assertEqual(detail.status_code, 403)
        self.assertEqual(listing.status_code, 403)


if __name__ == "__main__":
    unittest.main()
