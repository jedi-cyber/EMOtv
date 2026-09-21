from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from emotv.domain.consent_policy import ConsentPolicy

DEMO_POLICY_ID = "EMOTV-CONSENT-DEMO-001:v0.1"


class ConsentPolicyRepository(Protocol):
    def save(self, policy: ConsentPolicy) -> ConsentPolicy: ...
    def get(self, policy_id: str) -> ConsentPolicy | None: ...
    def active(self) -> ConsentPolicy | None: ...
    def list_all(self) -> tuple[ConsentPolicy, ...]: ...
    def activate(self, policy_id: str) -> ConsentPolicy: ...


class ConsentPolicyService:
    def __init__(self, repository: ConsentPolicyRepository, mode: str) -> None:
        if mode not in {"development", "demo", "production"}:
            raise ValueError("CONSENT_MODE debe ser development, demo o production")
        self.repository = repository
        self.mode = mode

    def active(self) -> ConsentPolicy | None:
        policy = self.repository.active()
        if policy is not None and policy.effective_at > datetime.now(timezone.utc):
            return None
        if self.mode == "production" and policy is not None and (policy.is_demo or not policy.approved):
            return None
        return policy

    def activate(self, policy_id: str) -> ConsentPolicy:
        policy = self.repository.get(policy_id)
        if policy is None:
            raise KeyError("Política no encontrada")
        if self.mode == "production" and (policy.is_demo or not policy.approved):
            raise ValueError("Producción requiere una política institucional aprobada")
        if policy.effective_at > datetime.now(timezone.utc):
            raise ValueError("La política todavía no está vigente")
        return self.repository.activate(policy_id)

    def ensure_demo_policy(self, path: Path) -> None:
        if self.mode != "demo" or self.repository.active() is not None:
            return
        if self.repository.get(DEMO_POLICY_ID) is None:
            self.repository.save(ConsentPolicy(
                id=DEMO_POLICY_ID, code="EMOTV-CONSENT-DEMO-001", version="v0.1",
                title="Consentimiento provisional de demostración",
                content=path.read_text(encoding="utf-8"),
                effective_at=datetime.now(timezone.utc), is_demo=True,
            ))
        self.repository.activate(DEMO_POLICY_ID)
