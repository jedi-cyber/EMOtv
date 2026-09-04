from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PostureResult:
    name: str
    detected: bool
    confidence: float = 0.0
    message: str = ""
