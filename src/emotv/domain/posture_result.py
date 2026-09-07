from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Sequence

from emotv.domain.posture_id import PostureId


@dataclass(frozen=True, slots=True)
class PostureResult:
    """Resultado genérico de evaluar una postura sobre landmarks corporales."""

    posture_id: PostureId | str
    detected: bool
    confidence: float = 0.0
    message: str = ""
    measurements: Mapping[str, float] = field(default_factory=dict)
    failed_rules: Sequence[str] = ()

    def __post_init__(self) -> None:
        posture_id = (
            PostureId(self.posture_id)
            if isinstance(self.posture_id, str)
            else self.posture_id
        )
        if not isinstance(posture_id, PostureId):
            raise TypeError("posture_id debe ser un PostureId válido")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence debe estar entre 0 y 1")

        object.__setattr__(self, "posture_id", posture_id)
        object.__setattr__(
            self,
            "measurements",
            MappingProxyType(dict(self.measurements)),
        )
        object.__setattr__(self, "failed_rules", tuple(self.failed_rules))

    @property
    def name(self) -> str:
        """Nombre serializable; mantiene compatibilidad con el modelo anterior."""

        assert isinstance(self.posture_id, PostureId)
        return self.posture_id.value

    @property
    def is_valid(self) -> bool:
        return self.detected
