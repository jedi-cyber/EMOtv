from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from emotv.domain.consent_policy import ConsentPolicy

DEMO_POLICY_CODE = "EMOTV-CONSENT-DEMO-002"
DEMO_POLICY_VERSION = "v0.2"
DEMO_POLICY_ID = f"{DEMO_POLICY_CODE}:{DEMO_POLICY_VERSION}"
DEMO_POLICY_TITLE = "Consentimiento de prueba para pruebas funcionales"


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
        """Publica la versión demo vigente en modo demo.

        Si no hay política activa o la activa es una demo anterior, registra la
        versión actual como política nueva y la activa; quienes aceptaron una
        versión anterior deben aceptar esta antes de su siguiente análisis. Las
        versiones anteriores quedan intactas y una política institucional
        activa nunca se reemplaza.
        """
        if self.mode != "demo":
            return
        active = self.repository.active()
        if active is not None and (not active.is_demo or active.id == DEMO_POLICY_ID):
            return
        if self.repository.get(DEMO_POLICY_ID) is None:
            self.repository.save(ConsentPolicy(
                id=DEMO_POLICY_ID, code=DEMO_POLICY_CODE, version=DEMO_POLICY_VERSION,
                title=DEMO_POLICY_TITLE,
                content=path.read_text(encoding="utf-8"),
                effective_at=datetime.now(timezone.utc), is_demo=True,
            ))
        self.repository.activate(DEMO_POLICY_ID)
