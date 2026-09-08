from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from emotv.application import AuthenticationService
from emotv.domain import Role, User
from emotv.interfaces.web.auth_router import create_auth_router


class Users:
    def __init__(self, items: tuple[User, ...] = ()) -> None:
        self.items = {item.id: item for item in items}
    def save(self, user: User) -> User: self.items[user.id] = user; return user
    def get_by_id(self, user_id: str) -> User | None: return self.items.get(user_id)
    def get_by_email(self, email: str) -> User | None:
        return next((x for x in self.items.values() if x.email == email), None)
    def list_all(self) -> tuple[User, ...]: return tuple(self.items.values())


class AuthRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = Users()
        cls.auth = AuthenticationService(
            cls.repository, "router-test-secret-at-least-32-characters"
        )
        now = datetime.now(timezone.utc)
        cls.student = User("student-user", "student@example.com",
            cls.auth.hash_password("student-password-123"), Role.STUDENT, now)
        cls.admin = User("admin-user", "admin@example.com",
            cls.auth.hash_password("administrator-password-123"), Role.ADMIN, now)
        cls.repository.save(cls.student)
        cls.repository.save(cls.admin)
        app = FastAPI()
        app.include_router(create_auth_router(cls.auth, cls.repository))
        cls.client = TestClient(app)

    def token(self, email: str, password: str) -> str:
        response = self.client.post("/auth/token", data={
            "username": email, "password": password,
        })
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    def test_oauth2_login_and_current_user(self) -> None:
        token = self.token("student@example.com", "student-password-123")
        response = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.student.id)
        self.assertNotIn("password_hash", response.json())

    def test_rejects_invalid_credentials_and_token(self) -> None:
        response = self.client.post("/auth/token", data={
            "username": "student@example.com", "password": "wrong",
        })
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get("/auth/me", headers={
            "Authorization": "Bearer invalid",
        }).status_code, 401)

    def test_admin_lists_users_but_student_is_forbidden(self) -> None:
        admin_token = self.token("admin@example.com", "administrator-password-123")
        student_token = self.token("student@example.com", "student-password-123")
        self.assertEqual(self.client.get("/auth/users", headers={
            "Authorization": f"Bearer {admin_token}",
        }).status_code, 200)
        self.assertEqual(self.client.get("/auth/users", headers={
            "Authorization": f"Bearer {student_token}",
        }).status_code, 403)

    def test_unconfigured_authentication_returns_service_unavailable(self) -> None:
        app = FastAPI()
        app.include_router(create_auth_router(None, None))
        with TestClient(app) as client:
            response = client.post("/auth/token", data={
                "username": "a@example.com", "password": "password",
            })
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__": unittest.main()
