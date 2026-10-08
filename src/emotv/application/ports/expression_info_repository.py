from __future__ import annotations

from typing import Protocol, runtime_checkable

from emotv.domain.expression_info import ExpressionInfo


@runtime_checkable
class ExpressionInfoRepository(Protocol):
    """Catálogo persistente de textos educativos por expresión."""

    def list_all(self) -> tuple[ExpressionInfo, ...]: ...

    def get(self, expression_key: str) -> ExpressionInfo | None: ...

    def save(self, info: ExpressionInfo) -> ExpressionInfo: ...
