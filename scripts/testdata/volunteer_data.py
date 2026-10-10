"""Cuentas de voluntarios (PRUEBA-NN) y eliminación verificable de sus datos.

Lo usan create_test_accounts.py y delete_test_data.py. La eliminación solo
toca cuentas con users.is_test_account verdadero, borra cada tabla de forma
explícita (sin depender de ON DELETE CASCADE ni de SET NULL) y verifica dentro
de la misma transacción que no quede ningún registro asociado: si algo falla,
no se borra nada.

Tablas con datos vinculados a un usuario o estudiante:

- users, students (código PRUEBA-NN), consents;
- sessions (sessions.student_id es SET NULL: se borran aquí para que no queden
  sesiones anónimas huérfanas);
- psychologist_assignments (como estudiante asignado o como psicólogo);
- login_attempts (sin clave foránea: se buscan por el SHA-256 del correo);
- chat_conversations y chat_messages;
- referencias de autoría que se anulan sin borrar la fila ajena:
  psychologist_assignments.assigned_by_user_id y
  expression_info.reviewed_by_user_id.

chat_rejection_counts no se vincula a usuarios (solo cuenta por categoría).
"""
from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Select, delete, false, func, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from emotv.application.login_throttle import hash_email
from emotv.infrastructure.persistence.models import (
    ChatConversationRecord,
    ChatMessageRecord,
    ConsentRecordModel,
    ExpressionInfoRecord,
    LoginAttemptRecord,
    PsychologistAssignmentRecord,
    SessionRecord,
    StudentRecord,
    UserRecord,
)

CODE_PREFIX = "PRUEBA-"
CODE_PATTERN = re.compile(r"^PRUEBA-(\d+)$")
EMAIL_DOMAIN = "emotv.local"
MAX_ACCOUNTS_PER_RUN = 50
DELETIONS_DIR = Path(__file__).resolve().parents[2] / "reports" / "deletions"

REASON_REQUEST = "solicitud del participante"
REASON_EXPIRED = "expirado"
REASON_CLOSING = "cierre de pruebas"

# Orden de borrado: primero las filas que dependen de otras.
TABLES = ("chat_messages", "chat_conversations", "sessions", "psychologist_assignments", "consents",
          "login_attempts", "students", "users")
REFERENCES = ("psychologist_assignments.assigned_by_user_id", "expression_info.reviewed_by_user_id")

BACKUP_WARNING = (
    "Advertencia: los respaldos hechos con scripts/docker/backup_db.py antes de esta eliminación "
    "(carpeta backups/) todavía contienen los datos de estas cuentas. Elimina o regenera los "
    "respaldos que tengan más de 30 días (docs/testing/volunteer-protocol.md)."
)


class VolunteerDataError(RuntimeError):
    """Operación rechazada; no se modificó la base de datos."""


class VerificationError(VolunteerDataError):
    """Quedaron registros asociados tras el borrado; la transacción se revierte."""


@dataclass(frozen=True)
class CreatedAccount:
    code: str
    email: str
    password: str
    created_at: datetime


@dataclass(frozen=True)
class VolunteerAccount:
    user_id: str
    student_id: str | None
    code: str
    email: str
    created_at: datetime


@dataclass(frozen=True)
class AccountDeletion:
    account: VolunteerAccount
    deleted: dict[str, int]
    remaining: dict[str, int]


@dataclass(frozen=True)
class DeletionReport:
    reason: str
    deleted_at: datetime
    accounts: tuple[AccountDeletion, ...]

    @property
    def verified(self) -> bool:
        return all(not any(item.remaining.values()) for item in self.accounts)


def code_for(number: int) -> str:
    return f"{CODE_PREFIX}{number:02d}"


def email_for(code: str) -> str:
    return f"{code.lower()}@{EMAIL_DOMAIN}"


def normalize_code(code: str) -> str:
    value = code.strip().upper()
    if not CODE_PATTERN.match(value):
        raise VolunteerDataError("El código debe tener la forma PRUEBA-NN")
    return value


def next_numbers(existing_codes: Iterable[str], count: int) -> range:
    """Números consecutivos a partir del mayor código PRUEBA-NN existente."""

    numbers = [int(match[1]) for code in existing_codes if (match := CODE_PATTERN.match(code))]
    start = max(numbers, default=0) + 1
    return range(start, start + count)


def create_test_accounts(
    factory: sessionmaker[Session],
    count: int,
    *,
    hash_password: Callable[[str], str],
    clock: Callable[[], datetime] | None = None,
    password_factory: Callable[[], str] = lambda: secrets.token_urlsafe(18),
    id_factory: Callable[[], str] = lambda: str(uuid4()),
) -> list[CreatedAccount]:
    """Crea cuentas de estudiante PRUEBA-NN sin consentimiento, en una transacción."""

    if not 1 <= count <= MAX_ACCOUNTS_PER_RUN:
        raise VolunteerDataError(f"--count debe estar entre 1 y {MAX_ACCOUNTS_PER_RUN}")
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    created = []
    with factory.begin() as db:
        codes = db.scalars(select(StudentRecord.student_code)
                           .where(StudentRecord.student_code.like(f"{CODE_PREFIX}%"))).all()
        for number in next_numbers(codes, count):
            code = code_for(number)
            email = email_for(code)
            if db.scalar(select(UserRecord.id).where(UserRecord.email == email)) is not None:
                raise VolunteerDataError(f"El correo {email} ya existe; no se creó ninguna cuenta")
            password = password_factory()
            user_id = f"user-{id_factory()}"
            db.add(UserRecord(id=user_id, email=email, password_hash=hash_password(password), role="student",
                              is_active=True, must_change_password=False, token_version=0, created_at=now,
                              is_test_account=True))
            db.flush()
            db.add(StudentRecord(id=f"student-{id_factory()}", user_id=user_id, student_code=code))
            created.append(CreatedAccount(code, email, password, now))
    return created


def find_by_code(db: Session, code: str) -> VolunteerAccount:
    row = db.execute(_accounts_query().where(StudentRecord.student_code == normalize_code(code))).first()
    if row is None:
        raise VolunteerDataError(f"No existe una cuenta con el código {normalize_code(code)}")
    if not row.is_test_account:
        raise VolunteerDataError(f"{normalize_code(code)} no es una cuenta de prueba (is_test_account=false); "
                            "no se elimina")
    return _account(row)


def find_test_accounts(db: Session, *, created_before: datetime | None = None) -> list[VolunteerAccount]:
    rows = db.execute(_accounts_query().where(UserRecord.is_test_account.is_(True))
                      .order_by(UserRecord.created_at, StudentRecord.student_code, UserRecord.id)).all()
    accounts = [_account(row) for row in rows]
    if created_before is not None:
        accounts = [item for item in accounts if item.created_at < created_before]
    return accounts


def count_remaining(db: Session, account: VolunteerAccount) -> dict[str, int]:
    """Registros asociados a la cuenta en cada tabla (y referencias de autoría)."""

    def total(query: Select) -> int:
        return db.scalar(select(func.count()).select_from(query.subquery())) or 0

    counts = {name: total(select(1).where(condition)) for name, condition in _conditions(account).items()}
    counts["psychologist_assignments.assigned_by_user_id"] = total(select(1).where(
        PsychologistAssignmentRecord.assigned_by_user_id == account.user_id))
    counts["expression_info.reviewed_by_user_id"] = total(select(1).where(
        ExpressionInfoRecord.reviewed_by_user_id == account.user_id))
    return counts


def delete_accounts(db: Session, accounts: Iterable[VolunteerAccount]) -> list[AccountDeletion]:
    """Borra cada cuenta dentro de la transacción de db y la verifica antes del commit."""

    results = []
    for account in accounts:
        deleted = delete_account(db, account)
        remaining = count_remaining(db, account)
        if any(remaining.values()):
            raise VerificationError(f"Quedan registros de {account.code}: {_nonzero(remaining)}")
        results.append(AccountDeletion(account, deleted, remaining))
    return results


def delete_account(db: Session, account: VolunteerAccount) -> dict[str, int]:
    deleted = {}
    # Primero se anulan las referencias de autoría: la fila es de otra persona.
    for name, model, column in (
        ("psychologist_assignments.assigned_by_user_id", PsychologistAssignmentRecord,
         PsychologistAssignmentRecord.assigned_by_user_id),
        ("expression_info.reviewed_by_user_id", ExpressionInfoRecord, ExpressionInfoRecord.reviewed_by_user_id),
    ):
        deleted[name] = db.execute(update(model).where(column == account.user_id)
                                   .values({column.key: None}), execution_options=_NO_SYNC).rowcount or 0
    for name, condition in _conditions(account).items():
        statement = delete(_MODELS[name]).where(condition)
        deleted[name] = db.execute(statement, execution_options=_NO_SYNC).rowcount or 0
    return deleted


def delete_test_data(
    factory: sessionmaker[Session],
    *,
    code: str | None = None,
    expired_before: datetime | None = None,
    all_accounts: bool = False,
    reason: str,
    clock: Callable[[], datetime] | None = None,
) -> DeletionReport:
    """Elimina en una sola transacción y vuelve a verificar después del commit."""

    if sum((code is not None, expired_before is not None, all_accounts)) != 1:
        raise VolunteerDataError("Indica exactamente un modo: --code, --expired o --all-test-accounts")
    deleted_at = (clock or (lambda: datetime.now(timezone.utc)))()
    with factory.begin() as db:
        if code is not None:
            accounts = [find_by_code(db, code)]
        else:
            accounts = find_test_accounts(db, created_before=expired_before)
        results = delete_accounts(db, accounts)
    with factory() as db:  # verificación independiente sobre lo ya confirmado
        checked = tuple(AccountDeletion(item.account, item.deleted, count_remaining(db, item.account))
                        for item in results)
    return DeletionReport(reason, deleted_at, checked)


def format_report(report: DeletionReport) -> str:
    lines = ["ACTA DE ELIMINACIÓN DE DATOS DE PRUEBA — EMOtv", "",
             f"Fecha y hora de eliminación: {_when(report.deleted_at)}",
             f"Motivo: {report.reason}",
             f"Cuentas eliminadas: {len(report.accounts)}"]
    for item in report.accounts:
        lines += ["", f"Código: {item.account.code}",
                  f"Cuenta creada: {_when(item.account.created_at)}",
                  "Registros eliminados por tabla:"]
        lines += [f"  - {name}: {item.deleted.get(name, 0)}" for name in TABLES]
        lines += [f"  - {name} (referencias anuladas): {item.deleted.get(name, 0)}" for name in REFERENCES]
        result = ("CORRECTA: 0 registros restantes en todas las tablas" if not any(item.remaining.values())
                  else f"FALLIDA: quedan registros ({_nonzero(item.remaining)})")
        lines.append(f"Verificación: {result}")
    lines += ["", f"Resultado general de la verificación: {'CORRECTA' if report.verified else 'FALLIDA'}",
              "", "Responsable de la eliminación: ______________________   Firma: ______________"]
    return "\n".join(lines)


def save_report(text: str, deleted_at: datetime, output_dir: Path = DELETIONS_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"acta-eliminacion-{deleted_at.astimezone():%Y%m%d-%H%M%S}.txt"
    path.write_text(text + "\n", encoding="utf-8")
    return path


# Sin objetos ORM cargados: no hace falta sincronizar la sesión.
_NO_SYNC = {"synchronize_session": False}

_MODELS = {
    "chat_messages": ChatMessageRecord,
    "chat_conversations": ChatConversationRecord,
    "sessions": SessionRecord,
    "psychologist_assignments": PsychologistAssignmentRecord,
    "consents": ConsentRecordModel,
    "login_attempts": LoginAttemptRecord,
    "students": StudentRecord,
    "users": UserRecord,
}


def _conditions(account: VolunteerAccount) -> dict[str, object]:
    student = account.student_id
    conversations = select(ChatConversationRecord.id).where(ChatConversationRecord.user_id == account.user_id)
    return {
        "chat_messages": ChatMessageRecord.conversation_id.in_(conversations),
        "chat_conversations": ChatConversationRecord.user_id == account.user_id,
        "sessions": SessionRecord.student_id == student if student else false(),
        "psychologist_assignments": or_(
            PsychologistAssignmentRecord.student_id == student if student else false(),
            PsychologistAssignmentRecord.psychologist_user_id == account.user_id),
        "consents": ConsentRecordModel.student_id == student if student else false(),
        "login_attempts": LoginAttemptRecord.email_hash == hash_email(account.email),
        "students": StudentRecord.user_id == account.user_id,
        "users": UserRecord.id == account.user_id,
    }


def _accounts_query() -> Select:
    return (select(UserRecord.id, UserRecord.email, UserRecord.created_at, UserRecord.is_test_account,
                   StudentRecord.id.label("student_id"), StudentRecord.student_code)
            .outerjoin(StudentRecord, StudentRecord.user_id == UserRecord.id))


def _account(row) -> VolunteerAccount:
    created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
    return VolunteerAccount(row.id, row.student_id, row.student_code or f"(sin código, {row.id})", row.email, created)


def _nonzero(counts: dict[str, int]) -> str:
    return ", ".join(f"{name}={value}" for name, value in counts.items() if value)


def _when(moment: datetime) -> str:
    return moment.astimezone().strftime("%Y-%m-%d %H:%M:%S (UTC%z)")


def retention_cutoff(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
