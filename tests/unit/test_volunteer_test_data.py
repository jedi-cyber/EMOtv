"""Cuentas de voluntarios PRUEBA-NN y su eliminación verificable (SQLite en memoria)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from emotv.application.login_throttle import hash_email
from emotv.config import get_test_data_retention_days
from emotv.infrastructure.persistence.models import (
    Base,
    ChatConversationRecord,
    ChatMessageRecord,
    ConsentRecordModel,
    LoginAttemptRecord,
    PsychologistAssignmentRecord,
    SessionRecord,
    StudentRecord,
    UserRecord,
)
from scripts.testdata import create_test_accounts as create_cli
from scripts.testdata import delete_test_data as delete_cli
from scripts.testdata import volunteer_data
from scripts.testdata.volunteer_data import TABLES, create_test_accounts

NOW = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _):  # ON DELETE como en PostgreSQL
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


def fake_hash(value: str) -> str:
    return f"sin-hash-{len(value)}"


def create(factory, count, at=NOW):
    return create_test_accounts(factory, count, hash_password=fake_hash, clock=lambda: at)


def add_regular_student(factory, code="PRUEBA-03"):
    """Cuenta sin is_test_account; se le da un código PRUEBA a propósito."""

    with factory.begin() as db:
        db.add(UserRecord(id="user-real", email="real@ejemplo.local", password_hash="x", role="student",
                          is_active=True, must_change_password=False, token_version=0,
                          created_at=NOW - timedelta(days=90)))
        db.flush()
        db.add(StudentRecord(id="student-real", user_id="user-real", student_code=code))
    add_activity(factory, "user-real", "student-real", "real@ejemplo.local", "real")


def add_activity(factory, user_id, student_id, email, tag):
    """Consentimiento, sesión, chat, intentos de login y asignación a un psicólogo."""

    with factory.begin() as db:
        if db.get(UserRecord, "user-psy") is None:
            db.add(UserRecord(id="user-psy", email="psicologia@ejemplo.local", password_hash="x",
                              role="psychologist", is_active=True, must_change_password=False, token_version=0,
                              created_at=NOW))
            db.flush()
        db.add(ConsentRecordModel(id=f"consent-{tag}", student_id=student_id, policy_version="demo-v0.3",
                                  granted_at=NOW))
        db.add(SessionRecord(id=f"session-{tag}", state="created", started_at=NOW, student_id=student_id))
        db.add(PsychologistAssignmentRecord(psychologist_user_id="user-psy", student_id=student_id,
                                            assigned_at=NOW, assigned_by_user_id=None))
        db.add(ChatConversationRecord(id=f"conv-{tag}", user_id=user_id, created_at=NOW, last_message_at=NOW))
        db.flush()
        for role in ("user", "assistant"):
            db.add(ChatMessageRecord(conversation_id=f"conv-{tag}", role=role, content="texto", in_scope=True,
                                     category="emotv", created_at=NOW))
        db.add(LoginAttemptRecord(id=f"login-{tag}", email_hash=hash_email(email), ip="127.0.0.1",
                                  created_at=NOW, success=True))


def activity_for(factory, account):
    with factory() as db:
        student_id = db.scalar(select(StudentRecord.id).where(StudentRecord.student_code == account.code))
        user_id = db.scalar(select(UserRecord.id).where(UserRecord.email == account.email))
    add_activity(factory, user_id, student_id, account.email, account.code)


def table_totals(factory):
    with factory() as db:
        return {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in (
            UserRecord, StudentRecord, ConsentRecordModel, SessionRecord, PsychologistAssignmentRecord,
            ChatConversationRecord, ChatMessageRecord, LoginAttemptRecord)}


def remaining(factory, account):
    """Registros asociados al código de la cuenta, o None si la cuenta ya no existe."""

    with factory() as db:
        row = db.execute(volunteer_data._accounts_query()
                         .where(StudentRecord.student_code == account.code)).first()
        return None if row is None else volunteer_data.count_remaining(db, volunteer_data._account(row))


def test_creates_consecutive_codes_after_the_last_existing_one(factory, capsys):
    add_regular_student(factory, "PRUEBA-03")
    first = create(factory, 2)
    assert [item.code for item in first] == ["PRUEBA-04", "PRUEBA-05"]
    assert [item.email for item in first] == ["prueba-04@emotv.local", "prueba-05@emotv.local"]
    assert len({item.password for item in first}) == 2

    assert create_cli.main(["--count", "1"], factory=factory) == 0
    output = capsys.readouterr().out
    assert "PRUEBA-06" in output and "prueba-06@emotv.local" in output

    with factory() as db:
        flags = dict(db.execute(select(StudentRecord.student_code, UserRecord.is_test_account)
                                .join(UserRecord, UserRecord.id == StudentRecord.user_id)).all())
        consents = db.scalar(select(func.count()).select_from(ConsentRecordModel)
                             .where(ConsentRecordModel.student_id != "student-real"))
    assert flags == {"PRUEBA-03": False, "PRUEBA-04": True, "PRUEBA-05": True, "PRUEBA-06": True}
    assert consents == 0  # el voluntario acepta el consentimiento en la aplicación


def test_create_cli_does_not_accept_names_or_emails(factory):
    with pytest.raises(SystemExit):
        create_cli.main(["--count", "1", "--email", "persona@ejemplo.org"], factory=factory)
    with pytest.raises(SystemExit):
        create_cli.main(["--count", "1", "--name", "Persona"], factory=factory)
    assert table_totals(factory)["users"] == 0


def test_delete_by_code_leaves_zero_records_in_every_table(factory, capsys, tmp_path):
    add_regular_student(factory)
    target, other = create(factory, 2)
    activity_for(factory, target)
    activity_for(factory, other)
    before = table_totals(factory)

    assert delete_cli.main(["--code", target.code.lower(), "--save"], factory=factory,
                           clock=lambda: NOW, output_dir=tmp_path / "deletions") == 0

    assert remaining(factory, target) is None
    with factory() as db:
        conversations = db.scalar(select(func.count()).select_from(ChatConversationRecord)
                                  .where(ChatConversationRecord.id == f"conv-{target.code}"))
        sessions = db.scalar(select(func.count()).select_from(SessionRecord)
                             .where(SessionRecord.id == f"session-{target.code}"))
        orphan_sessions = db.scalar(select(func.count()).select_from(SessionRecord)
                                    .where(SessionRecord.student_id.is_(None)))
    assert conversations == sessions == orphan_sessions == 0
    after = table_totals(factory)
    assert after == {name: value - {"users": 1, "students": 1, "consents": 1, "sessions": 1,
                                    "psychologist_assignments": 1, "chat_conversations": 1,
                                    "chat_messages": 2, "login_attempts": 1}[name]
                     for name, value in before.items()}
    assert remaining(factory, other)["users"] == 1  # la otra cuenta sigue intacta

    output = capsys.readouterr().out
    assert target.code in output and "Motivo: solicitud del participante" in output
    assert "chat_messages: 2" in output and "Verificación: CORRECTA" in output
    assert "backup_db.py" in output
    saved = Path(output.split("Acta guardada en ", 1)[1].splitlines()[0])
    assert saved.parent == tmp_path / "deletions" and saved.name.startswith("acta-eliminacion-")
    acta = saved.read_text(encoding="utf-8")
    assert target.code in acta and "Resultado general de la verificación: CORRECTA" in acta
    assert target.password not in output + acta


def test_expired_respects_the_retention_period(factory, monkeypatch, capsys):
    monkeypatch.delenv("TEST_DATA_RETENTION_DAYS", raising=False)
    (old,) = create(factory, 1, at=NOW - timedelta(days=31))
    (recent,) = create(factory, 1, at=NOW - timedelta(days=29))
    activity_for(factory, old)

    assert delete_cli.main(["--expired"], factory=factory, clock=lambda: NOW) == 0
    assert "Motivo: expirado" in capsys.readouterr().out
    assert remaining(factory, old) is None
    assert remaining(factory, recent)["users"] == 1

    monkeypatch.setenv("TEST_DATA_RETENTION_DAYS", "7")
    assert delete_cli.main(["--expired"], factory=factory, clock=lambda: NOW) == 0
    assert remaining(factory, recent) is None


def test_retention_cannot_exceed_the_consent_promise():
    assert get_test_data_retention_days({}) == 30
    assert get_test_data_retention_days({"TEST_DATA_RETENTION_DAYS": "10"}) == 10
    for value in ("0", "31", "x"):
        with pytest.raises(ValueError):
            get_test_data_retention_days({"TEST_DATA_RETENTION_DAYS": value})


def test_account_without_test_flag_is_never_deleted(factory, capsys):
    add_regular_student(factory, "PRUEBA-03")
    before = table_totals(factory)

    assert delete_cli.main(["--code", "PRUEBA-03"], factory=factory, clock=lambda: NOW) == 1
    assert "no es una cuenta de prueba" in capsys.readouterr().err
    assert delete_cli.main(["--all-test-accounts"], factory=factory, ask=lambda _: "ELIMINAR",
                           clock=lambda: NOW) == 0
    assert delete_cli.main(["--expired"], factory=factory, clock=lambda: NOW + timedelta(days=400)) == 0
    assert table_totals(factory) == before


def test_all_test_accounts_requires_typing_eliminar(factory):
    create(factory, 2)
    assert delete_cli.main(["--all-test-accounts"], factory=factory, ask=lambda _: "si") == 1
    assert table_totals(factory)["users"] == 2
    assert delete_cli.main(["--all-test-accounts"], factory=factory, ask=lambda _: "ELIMINAR") == 0
    assert table_totals(factory)["users"] == 0


def test_failure_halfway_deletes_nothing(factory, monkeypatch):
    accounts = create(factory, 2)
    for account in accounts:
        activity_for(factory, account)
    before = table_totals(factory)
    original, calls = volunteer_data.delete_account, []

    def fail_on_second(db, account):
        calls.append(account.code)
        result = original(db, account)
        if len(calls) == 2:
            raise RuntimeError("fallo simulado")
        return result

    monkeypatch.setattr(volunteer_data, "delete_account", fail_on_second)
    with pytest.raises(RuntimeError):
        delete_cli.main(["--all-test-accounts"], factory=factory, ask=lambda _: "ELIMINAR")
    assert calls == ["PRUEBA-01", "PRUEBA-02"]
    assert table_totals(factory) == before


def test_records_left_after_delete_roll_back_everything(factory, monkeypatch, capsys):
    (account,) = create(factory, 1)
    activity_for(factory, account)
    before = table_totals(factory)
    monkeypatch.setattr(volunteer_data, "count_remaining", lambda db, item: {name: 0 for name in TABLES}
                        | {"sessions": 1})

    assert delete_cli.main(["--code", account.code], factory=factory) == 1
    assert "Quedan registros" in capsys.readouterr().err
    assert table_totals(factory) == before
