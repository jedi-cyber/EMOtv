"""Modelo local predeterminado y su respaldo, según la admisión vigente.

La configuración se lee en cada inicio de sesión, así un cambio del
superadministrador rige sin reiniciar el servidor (y en todos sus procesos).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import logging

from emotv.application.ports.local_model_settings_repository import LocalModelSettingsRepository
from emotv.domain.local_model_settings import LocalModelSettings

HSEMOTION_MODEL_ID = "hsemotion_enet_b0_8_best_afew"
FERPLUS_MODEL_ID = "ferplus_onnx"
# Únicos modelos de expresión que pueden ser predeterminados o elegirse en una sesión.
LOCAL_MODEL_IDS = (HSEMOTION_MODEL_ID, FERPLUS_MODEL_ID)
INITIAL_DEFAULT_MODEL_ID = HSEMOTION_MODEL_ID
ADMITTED_STATES = ("SUPPORTED", "WARNING")

Admission = Callable[[str], dict]
Clock = Callable[[], datetime]

logger = logging.getLogger(__name__)


class ModelNotAdmitted(ValueError):
    """El modelo no tiene una admisión vigente en este servidor."""

    def __init__(self, admission: dict | None) -> None:
        reasons = (admission or {}).get("reasons") or ["Evaluación de modelos no configurada"]
        super().__init__("Modelo sin admisión vigente: " + "; ".join(reasons))
        self.admission = admission


@dataclass(frozen=True, slots=True)
class ModelChoice:
    """Modelo resuelto para una sesión; admission es None si no hay evaluación configurada."""

    model_id: str
    admission: dict | None
    fallback: bool = False

    @property
    def admitted(self) -> bool:
        return is_admitted(self.admission)


def is_admitted(admission: dict | None) -> bool:
    return admission is None or admission.get("state") in ADMITTED_STATES


class LocalModelService:
    def __init__(
        self,
        repository: LocalModelSettingsRepository | None = None,
        admission: Admission | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository
        self.admission = admission
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def settings(self) -> LocalModelSettings:
        stored = self.repository.get() if self.repository is not None else None
        return stored or LocalModelSettings(INITIAL_DEFAULT_MODEL_ID)

    def evaluate(self, model_id: str) -> dict | None:
        return self.admission(model_id) if self.admission is not None else None

    def status(self) -> tuple[tuple[str, dict | None, bool], ...]:
        """(modelo, admisión, es predeterminado) para cada modelo local."""
        default = self.settings().default_model_id
        return tuple((model_id, self.evaluate(model_id), model_id == default) for model_id in LOCAL_MODEL_IDS)

    def set_default(self, model_id: str, actor_user_id: str) -> LocalModelSettings:
        if model_id not in LOCAL_MODEL_IDS:
            raise KeyError(model_id)
        if self.repository is None:
            raise RuntimeError("Configuración de modelos no disponible")
        admission = self.evaluate(model_id)
        # Sin evaluación configurada no hay forma de comprobar la admisión.
        if admission is None or not is_admitted(admission):
            raise ModelNotAdmitted(admission)
        # Una configuración nueva deja atrás el último uso del respaldo.
        return self.repository.save(LocalModelSettings(
            default_model_id=model_id, changed_by_user_id=actor_user_id, changed_at=self.clock(),
        ))

    def resolve(self, requested: str | None = None) -> ModelChoice:
        """Modelo pedido para la sesión o, sin pedido, el predeterminado con su respaldo.

        Quien llama decide qué hacer si el resultado no está admitido.
        """
        if requested is not None:
            return ModelChoice(requested, self.evaluate(requested))
        settings = self.settings()
        default = settings.default_model_id
        choice = ModelChoice(default, self.evaluate(default))
        if choice.admitted:
            return choice
        backup = next(model_id for model_id in LOCAL_MODEL_IDS if model_id != default)
        fallback = ModelChoice(backup, self.evaluate(backup), fallback=True)
        if fallback.admitted:
            self._record_fallback(settings, backup, choice.admission)
        return fallback

    def _record_fallback(self, settings: LocalModelSettings, backup: str, admission: dict | None) -> None:
        reasons = "; ".join((admission or {}).get("reasons") or [])
        logger.warning("El modelo predeterminado %s no tiene admisión vigente (%s); se usa %s",
                       settings.default_model_id, reasons or "sin detalle", backup)
        if self.repository is None:
            return
        try:
            self.repository.save(replace(settings, fallback_model_id=backup, fallback_at=self.clock()))
        except Exception:
            # El registro no debe impedir la sesión: el log ya conserva el evento.
            logger.exception("No se pudo registrar el uso del modelo de respaldo")
