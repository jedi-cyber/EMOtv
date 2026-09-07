from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StabilizedEmotion:
    """Emoción dominante obtenida a partir de varias predicciones."""

    emotion: str
    confidence: float
    agreement: float
    votes: int
    samples: int

    def __post_init__(self) -> None:
        if not self.emotion.strip():
            raise ValueError("emotion no puede estar vacía")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence debe estar entre 0 y 1")
        if not 0.0 <= self.agreement <= 1.0:
            raise ValueError("agreement debe estar entre 0 y 1")
        if self.votes < 1 or self.samples < self.votes:
            raise ValueError("votes y samples no son coherentes")

        object.__setattr__(self, "emotion", self.emotion.strip().lower())
