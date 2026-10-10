"""Conexión de los scripts de datos de prueba: solo a PostgreSQL local."""
from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from emotv.config import get_database_url
from emotv.infrastructure.persistence import create_database_engine, create_session_factory
from scripts.create_demo_role_accounts import allowed_hosts


@contextmanager
def open_database(parser: argparse.ArgumentParser,
                  factory: sessionmaker[Session] | None = None) -> Iterator[sessionmaker[Session]]:
    """Usa factory si se pasa (pruebas); si no, DATABASE_URL con host local y migraciones al día."""

    if factory is not None:
        yield factory
        return
    database_url = get_database_url()
    if make_url(database_url).host not in allowed_hosts():
        parser.error("Este script solo permite una base de datos local (o ALLOWED_ADMIN_RESET_HOSTS)")
    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("users")} \
            if inspector.has_table("users") else set()
        if "is_test_account" not in columns:
            parser.error("Falta users.is_test_account; aplica las migraciones (python -m alembic upgrade head)")
        yield create_session_factory(engine)
    finally:
        engine.dispose()
