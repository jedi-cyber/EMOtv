from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmotionModel:
    """Metadatos públicos de un modelo seleccionable de emociones faciales."""

    id: str
    name: str
    description: str
    version: str
    input_size: tuple[int, int]
    emotion_labels: tuple[str, ...]
    is_default: bool = False

    def __post_init__(self) -> None:
        for field_name in ("id", "name", "description", "version"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise TypeError(f"{field_name} debe ser str")
            normalized = value.strip()
            if not normalized:
                raise ValueError(f"{field_name} no puede estar vacío")
            object.__setattr__(self, field_name, normalized)

        if (
            not isinstance(self.input_size, tuple)
            or len(self.input_size) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in self.input_size
            )
        ):
            raise ValueError("input_size debe contener dos enteros positivos")

        if not isinstance(self.emotion_labels, tuple) or not self.emotion_labels:
            raise ValueError("emotion_labels debe ser una tupla no vacía")
        normalized_labels: list[str] = []
        for label in self.emotion_labels:
            if not isinstance(label, str):
                raise TypeError("cada etiqueta emocional debe ser str")
            normalized = label.strip().lower()
            if not normalized:
                raise ValueError("las etiquetas emocionales no pueden estar vacías")
            if normalized in normalized_labels:
                raise ValueError(f"Etiqueta emocional duplicada: {normalized}")
            normalized_labels.append(normalized)

        if not isinstance(self.is_default, bool):
            raise TypeError("is_default debe ser bool")
        object.__setattr__(self, "emotion_labels", tuple(normalized_labels))
