"""Validación de los modelos con adultos voluntarios, antes de usar la práctica con niños.

Mide si cada modelo reconoce expresiones producidas a propósito. El protocolo
«Validación con adultos» tiene un ejercicio por cada expresión que se puede pedir
y solo existe en CONSENT_MODE demo, para cuentas de voluntarios (PRUEBA-NN). La
exportación es agregada, solo para administración (superadmin): por modelo y
expresión pedida, sin códigos de sesión ni nada que identifique a alguien. No se
guarda ningún archivo en el servidor: el CSV se arma en memoria al pedirlo. Ver
docs/expression-practice.md.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.session_metrics import APPLIED
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.expression_info import EXPRESSION_KEYS
from emotv.domain.guided_session import PracticeResult
from emotv.domain.protocol import Protocol, ProtocolKind, ProtocolStep
from emotv.domain.role import Role
from emotv.domain.session import EmotionalSession
from emotv.domain.user import User

VALIDATION_PROTOCOL_NAME = "Validación con adultos"
VALIDATION_DESCRIPTION = ("Un ejercicio por expresión, para medir si el modelo reconoce expresiones producidas a "
                          "propósito. Solo con adultos voluntarios (cuentas PRUEBA-NN). No se guardan imágenes.")
# Todas las expresiones del modelo menos desprecio, en su orden.
VALIDATION_TARGETS = tuple(key for key in EXPRESSION_KEYS if key != "contempt")
VALIDATION_HOLD_SECONDS = 2
VALIDATION_MAX_SECONDS = 15
DEMO = "demo"
RESOURCE = "practice_validation"
CSV_HEADER = ("modelo", "version_modelo", "expresion_pedida", "ejercicios", "logrados",
              "tiempo_promedio_hasta_lograrlo_s")


def is_validation_protocol(protocol: Protocol) -> bool:
    return protocol.name.strip().casefold() == VALIDATION_PROTOCOL_NAME.casefold()


def validation_steps() -> tuple[ProtocolStep, ...]:
    return tuple(ProtocolStep.practice(target, VALIDATION_HOLD_SECONDS, VALIDATION_MAX_SECONDS)
                 for target in VALIDATION_TARGETS)


def validation_rows(results: Iterable[PracticeResult]) -> list[tuple[str, str, str, int, int, str]]:
    """Por modelo, versión y expresión pedida: ejercicios terminados (logrados o con
    el tiempo vencido), logrados y tiempo promedio hasta lograrlo (solo los logrados)."""
    groups: dict[tuple[str, str, str], list[PracticeResult]] = {}
    for item in results:
        if item.outcome in APPLIED:
            groups.setdefault((item.emotion_model_id, item.emotion_model_version, item.target_expression), []).append(item)
    order = {key: index for index, key in enumerate(EXPRESSION_KEYS)}
    rows = []
    for (model, version, target), items in sorted(groups.items(),
                                                  key=lambda entry: (entry[0][0], entry[0][1], order.get(entry[0][2], 99))):
        achieved = [item.seconds_to_achieve for item in items if item.achieved and item.seconds_to_achieve is not None]
        average = f"{sum(achieved) / len(achieved):.2f}" if achieved else ""
        rows.append((model, version, target, len(items), len(achieved), average))
    return rows


class PracticeValidationService:
    def __init__(
        self,
        protocols,                                      # ProtocolRepository
        sessions,                                       # SessionService
        guided,                                         # repositorio de la sesión guiada
        audit: AuditService,
        consent_mode: str,
        is_test_account: Callable[[str], bool],
        test_account_ids: Callable[[], Iterable[str]],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.protocols = protocols
        self.sessions = sessions
        self.guided = guided
        self.audit = audit
        self.consent_mode = consent_mode
        self.is_test_account = is_test_account
        self.test_account_ids = test_account_ids
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Protocolo de ejemplo ------------------------------------------------------------

    def available(self, user: User) -> bool:
        """Solo en modo demo y para una cuenta de voluntario activa."""
        return (self.consent_mode == DEMO and user.is_active and user.role is Role.STUDENT
                and self.is_test_account(user.id))

    def usable(self, protocol: Protocol) -> bool:
        """Un protocolo de validación solo se aplica mientras su dueño cumpla las condiciones."""
        return self.consent_mode == DEMO and self.is_test_account(protocol.owner_user_id)

    def current_protocol(self, user: User) -> Protocol | None:
        return next((item for item in self.protocols.list_current((user.id,))
                     if item.kind is ProtocolKind.PRACTICE and is_validation_protocol(item)), None)

    def ensure_protocol(self, user: User) -> Protocol:
        """Agrega el protocolo a la cuenta, o devuelve el que ya tiene."""
        if not self.available(user):
            raise PermissionError("El protocolo de validación es solo para cuentas de voluntarios en modo demo")
        found = self.current_protocol(user)
        if found is not None:
            return found
        family = str(uuid4())
        protocol = self.protocols.add(Protocol(
            id=family, family_id=family, version=1, owner_user_id=user.id, name=VALIDATION_PROTOCOL_NAME,
            description=VALIDATION_DESCRIPTION, for_children=False, created_at=self.clock(), steps=validation_steps()))
        self.audit.record(user, AuditAction.CREATE, "protocol", protocol.id)
        return protocol

    # --- Exportación agregada -------------------------------------------------------------

    def _validation_sessions(self) -> list[EmotionalSession]:
        found = []
        for owner in self.test_account_ids():
            for session in self.sessions.list_sessions_by_owner(owner):
                protocol = self.protocols.get(session.protocol_id) if session.protocol_id else None
                if protocol is not None and is_validation_protocol(protocol):
                    found.append(session)
        return found

    def export_csv(self, user: User) -> str:
        """CSV agregado de las sesiones de validación. Solo administración (superadmin)."""
        if not user.is_active or user.role is not Role.SUPERADMIN:
            self.audit.record(user, AuditAction.VIEW, RESOURCE, None, AuditResult.DENIED)
            raise PermissionError("Solo administración exporta la validación de los modelos")
        results = [item for session in self._validation_sessions()
                   for item in self.guided.list_practice_results(session.id)]
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        writer.writerows(validation_rows(results))
        self.audit.record(user, AuditAction.VIEW, RESOURCE, None)
        return buffer.getvalue()
