from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class RecommendationSource(Protocol):
    """Lectura de asociaciones expresión -> actividades, en orden de prioridad."""

    def activity_ids_for(self, expression_key: str) -> tuple[str, ...]: ...


@runtime_checkable
class RecommendationRepository(RecommendationSource, Protocol):
    """Asociaciones editables por administración."""

    def list_all(self) -> dict[str, tuple[str, ...]]: ...

    def replace(self, expression_key: str, activity_ids: Sequence[str]) -> tuple[str, ...]:
        """Sustituye todas las asociaciones de una expresión; el orden es la prioridad."""
        ...

    def expressions_using(self, activity_id: str) -> tuple[str, ...]: ...
