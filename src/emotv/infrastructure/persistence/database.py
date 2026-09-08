from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from emotv.config import get_database_url


def create_database_engine(
    database_url: str | None = None,
    *,
    echo: bool = False,
) -> Engine:
    """Crea el engine sin establecer una conexión hasta su primer uso."""

    url = database_url.strip() if database_url is not None else get_database_url()
    if not url:
        raise ValueError("database_url no puede estar vacía")
    return create_engine(url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Construye sesiones transaccionales para los repositorios SQLAlchemy."""

    if not isinstance(engine, Engine):
        raise TypeError("engine debe ser un Engine de SQLAlchemy")
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )
