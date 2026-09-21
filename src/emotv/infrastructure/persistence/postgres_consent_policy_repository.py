from __future__ import annotations

from datetime import timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from emotv.domain.consent_policy import ConsentPolicy
from emotv.infrastructure.persistence.models import ConsentPolicyRecord


class PostgresConsentPolicyRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def save(self, policy: ConsentPolicy) -> ConsentPolicy:
        with self._factory.begin() as db:
            if db.get(ConsentPolicyRecord, policy.id) is not None:
                raise ValueError("La versión de política ya existe y no puede sobrescribirse")
            db.add(ConsentPolicyRecord(id=policy.id, code=policy.code,
                version=policy.version, title=policy.title, content=policy.content,
                effective_at=policy.effective_at, is_demo=policy.is_demo,
                approved=policy.approved, is_active=policy.is_active))
        return policy

    def get(self, policy_id: str) -> ConsentPolicy | None:
        with self._factory() as db:
            row = db.get(ConsentPolicyRecord, policy_id)
            return self._domain(row) if row else None

    def active(self) -> ConsentPolicy | None:
        with self._factory() as db:
            row = db.scalar(select(ConsentPolicyRecord).where(ConsentPolicyRecord.is_active.is_(True)))
            return self._domain(row) if row else None

    def list_all(self) -> tuple[ConsentPolicy, ...]:
        with self._factory() as db:
            rows = db.scalars(select(ConsentPolicyRecord).order_by(ConsentPolicyRecord.effective_at.desc())).all()
            return tuple(self._domain(row) for row in rows)

    def activate(self, policy_id: str) -> ConsentPolicy:
        with self._factory.begin() as db:
            row = db.get(ConsentPolicyRecord, policy_id)
            if row is None:
                raise KeyError("Política no encontrada")
            db.execute(update(ConsentPolicyRecord).values(is_active=False))
            row.is_active = True
        return self.active()  # type: ignore[return-value]

    @staticmethod
    def _domain(row: ConsentPolicyRecord) -> ConsentPolicy:
        effective = row.effective_at if row.effective_at.tzinfo else row.effective_at.replace(tzinfo=timezone.utc)
        return ConsentPolicy(row.id, row.code, row.version, row.title, row.content,
                             effective, row.is_demo, row.approved, row.is_active)
