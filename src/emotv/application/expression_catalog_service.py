from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone

from emotv.application.ports.expression_info_repository import ExpressionInfoRepository
from emotv.domain.expression_info import EXPRESSION_KEYS, ExpressionInfo, ReviewStatus

Clock = Callable[[], datetime]


class ExpressionCatalogService:
    """Consulta y edición del catálogo informativo; no usa ningún LLM."""

    def __init__(self, repository: ExpressionInfoRepository, clock: Clock | None = None) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def list_all(self) -> tuple[ExpressionInfo, ...]:
        order = {key: index for index, key in enumerate(EXPRESSION_KEYS)}
        return tuple(sorted(self.repository.list_all(), key=lambda item: order[item.expression_key]))

    def get(self, expression_key: str) -> ExpressionInfo | None:
        return self.repository.get(expression_key.strip().lower())

    def update(
        self,
        expression_key: str,
        *,
        editor_user_id: str,
        review_status: ReviewStatus | str,
        **texts: str,
    ) -> ExpressionInfo:
        """Reemplaza los textos. Marcar "reviewed" registra quién y cuándo;
        guardar como borrador elimina una revisión anterior."""
        current = self.get(expression_key)
        if current is None:
            raise KeyError(expression_key)
        status = ReviewStatus(review_status)
        now = self.clock()
        reviewed = status is ReviewStatus.REVIEWED
        return self.repository.save(replace(
            current,
            **texts,
            review_status=status,
            reviewed_by_user_id=editor_user_id if reviewed else None,
            reviewed_at=now if reviewed else None,
            updated_at=now,
        ))
