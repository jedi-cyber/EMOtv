from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

from emotv.config import (
    EMOTION_STABILIZER_MIN_AGREEMENT,
    EMOTION_STABILIZER_MIN_CONFIDENCE,
    EMOTION_STABILIZER_MIN_SAMPLES,
    EMOTION_STABILIZER_WINDOW_SIZE,
)
from emotv.domain.stabilized_emotion import StabilizedEmotion


@dataclass(frozen=True, slots=True)
class EmotionObservation:
    emotion: str
    confidence: float


class EmotionStabilizer:
    """Obtiene una emoción estable desde una ventana de predicciones."""

    def __init__(
        self,
        window_size: int = EMOTION_STABILIZER_WINDOW_SIZE,
        min_samples: int = EMOTION_STABILIZER_MIN_SAMPLES,
        min_confidence: float = EMOTION_STABILIZER_MIN_CONFIDENCE,
        min_agreement: float = EMOTION_STABILIZER_MIN_AGREEMENT,
    ) -> None:
        if window_size < 1:
            raise ValueError("window_size debe ser mayor que cero")
        if not 1 <= min_samples <= window_size:
            raise ValueError("min_samples debe estar entre 1 y window_size")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence debe estar entre 0 y 1")
        if not 0.0 < min_agreement <= 1.0:
            raise ValueError("min_agreement debe estar entre 0 y 1")

        self.window_size = window_size
        self.min_samples = min_samples
        self.min_confidence = min_confidence
        self.min_agreement = min_agreement
        self._observations: deque[EmotionObservation] = deque(maxlen=window_size)

    @property
    def sample_count(self) -> int:
        return len(self._observations)

    def update(self, emotion: str, confidence: float) -> StabilizedEmotion | None:
        normalized_emotion = emotion.strip().lower()
        if not normalized_emotion:
            raise ValueError("emotion no puede estar vacía")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence debe estar entre 0 y 1")

        self._observations.append(
            EmotionObservation(normalized_emotion, float(confidence)),
        )
        return self.current()

    def current(self) -> StabilizedEmotion | None:
        eligible = tuple(
            observation
            for observation in self._observations
            if observation.confidence >= self.min_confidence
        )
        if len(eligible) < self.min_samples:
            return None

        counts = Counter(observation.emotion for observation in eligible)
        highest_votes = max(counts.values())
        winners = tuple(
            emotion for emotion, votes in counts.items() if votes == highest_votes
        )
        if len(winners) != 1:
            return None

        winner = winners[0]
        agreement = highest_votes / len(eligible)
        if agreement < self.min_agreement:
            return None

        winner_confidences = [
            observation.confidence
            for observation in eligible
            if observation.emotion == winner
        ]
        return StabilizedEmotion(
            emotion=winner,
            confidence=sum(winner_confidences) / len(winner_confidences),
            agreement=agreement,
            votes=highest_votes,
            samples=len(eligible),
        )

    def reset(self) -> None:
        self._observations.clear()
