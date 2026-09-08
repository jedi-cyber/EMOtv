from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from emotv.application import ActivityCatalog, AuthenticationService
from emotv.domain import Role, User
from emotv.interfaces.web.activity_router import create_activity_router


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    def save(self, user: User) -> User:
        self.users[user.id] = user
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    def list_all(self) -> tuple[User, ...]:
        return tuple(self.users.values())


class ActivityRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.users = FakeUserRepository()
        self.authentication = AuthenticationService(
            self.users, "unit-test-jwt-secret-with-at-least-32-characters"
        )
        now = datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.admin = User("admin", "admin@example.com", "hash", Role.ADMIN, now)
        self.student = User(
            "student", "student@example.com", "hash", Role.STUDENT, now
        )
        self.users.save(self.admin)
        self.users.save(self.student)
        app = FastAPI()
        app.include_router(create_activity_router(
            ActivityCatalog(()), self.authentication, self.users
        ))
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def headers(self, user: User) -> dict[str, str]:
        token = self.authentication.create_access_token(user)
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def payload(name: str = "Respiración corporal") -> dict[str, object]:
        return {
            "id": "custom_activity",
            "name": name,
            "description": "Mantén los brazos abiertos.",
            "required_posture": "arms_open",
            "duration_seconds": 8.0,
            "repetitions": 2,
        }

    def test_admin_manages_activity_lifecycle(self) -> None:
        headers = self.headers(self.admin)

        created = self.client.post("/activities", json=self.payload(), headers=headers)
        listed = self.client.get("/activities", headers=headers)
        detail = self.client.get("/activities/custom_activity", headers=headers)
        updated = self.client.put(
            "/activities/custom_activity",
            json=self.payload("Actividad actualizada"),
            headers=headers,
        )
        deleted = self.client.delete("/activities/custom_activity", headers=headers)
        missing = self.client.get("/activities/custom_activity", headers=headers)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(detail.json()["required_posture"], "arms_open")
        self.assertEqual(updated.json()["name"], "Actividad actualizada")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(missing.status_code, 404)

    def test_student_can_read_but_cannot_modify_activities(self) -> None:
        headers = self.headers(self.student)

        self.assertEqual(self.client.get("/activities", headers=headers).status_code, 200)
        self.assertEqual(
            self.client.post("/activities", json=self.payload(), headers=headers).status_code,
            403,
        )

    def test_requires_authentication(self) -> None:
        self.assertEqual(self.client.get("/activities").status_code, 401)


if __name__ == "__main__":
    unittest.main()
