from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from emotv.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)


class DatabaseTests(unittest.TestCase):
    def test_creates_engine_without_opening_connection(self) -> None:
        engine = create_database_engine("sqlite+pysqlite:///:memory:")

        try:
            self.assertEqual(engine.url.drivername, "sqlite+pysqlite")
            self.assertTrue(engine.pool._pre_ping)  # type: ignore[attr-defined]
        finally:
            engine.dispose()

    def test_creates_configured_session_factory(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        factory = create_session_factory(engine)

        try:
            with factory() as session:
                self.assertIsInstance(session, Session)
                self.assertFalse(session.expire_on_commit)
                self.assertFalse(session.autoflush)
        finally:
            engine.dispose()

    def test_rejects_empty_explicit_database_url(self) -> None:
        with self.assertRaises(ValueError):
            create_database_engine("   ")

    def test_rejects_invalid_engine_for_session_factory(self) -> None:
        with self.assertRaises(TypeError):
            create_session_factory(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
