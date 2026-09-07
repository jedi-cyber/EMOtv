from __future__ import annotations

from dataclasses import dataclass

from emotv.domain.posture_id import PostureId


@dataclass(frozen=True, slots=True)
class Activity:
    """Actividad local que el usuario debe realizar."""

    id: str
    name: str
    description: str
    required_posture: PostureId | str
    duration_seconds: float
    repetitions: int = 1

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id no puede estar vacío")
        if not self.name.strip():
            raise ValueError("name no puede estar vacío")
        if not self.description.strip():
            raise ValueError("description no puede estar vacía")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds debe ser mayor que cero")
        if (
            isinstance(self.repetitions, bool)
            or not isinstance(self.repetitions, int)
            or self.repetitions < 1
        ):
            raise ValueError("repetitions debe ser un entero mayor o igual que uno")

        posture_id = (
            PostureId(self.required_posture)
            if isinstance(self.required_posture, str)
            else self.required_posture
        )
        if not isinstance(posture_id, PostureId):
            raise TypeError("required_posture debe ser un PostureId válido")

        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "required_posture", posture_id)
        object.__setattr__(self, "duration_seconds", float(self.duration_seconds))
