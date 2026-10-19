from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class LocalModelSettings:
    """Modelo local predeterminado, quién lo eligió y el último uso del respaldo.

    changed_by_user_id y changed_at son nulos mientras rige el valor inicial.
    fallback_model_id y fallback_at registran la última vez que el sistema usó
    el otro modelo porque el predeterminado no tenía admisión vigente.
    """

    default_model_id: str
    changed_by_user_id: str | None = None
    changed_at: datetime | None = None
    fallback_model_id: str | None = None
    fallback_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.default_model_id, str) or not self.default_model_id.strip():
            raise ValueError("default_model_id no puede estar vacío")
        for name in ("changed_at", "fallback_at"):
            value = getattr(self, name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} debe incluir zona horaria")
        if (self.fallback_model_id is None) != (self.fallback_at is None):
            raise ValueError("fallback_model_id y fallback_at deben registrarse juntos")
