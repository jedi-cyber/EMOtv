from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Exercise:
    id: str
    name: str
    description: str

    required_posture: str

    duration_seconds: float = 0.0
    repetitions: int = 1
