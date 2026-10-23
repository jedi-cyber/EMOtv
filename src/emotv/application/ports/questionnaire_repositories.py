from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol as Interface

from emotv.domain.questionnaire import Questionnaire, QuestionnaireResponse


class QuestionnaireRepository(Interface):
    def add(self, questionnaire: Questionnaire) -> Questionnaire: ...

    def replace(self, questionnaire: Questionnaire) -> Questionnaire:
        """Reemplaza una versión que nunca se usó."""
        ...

    def add_version(self, previous_id: str, superseded_at: datetime, questionnaire: Questionnaire) -> Questionnaire:
        """Marca la versión anterior como reemplazada y guarda la nueva, en una transacción."""
        ...

    def get(self, questionnaire_id: str) -> Questionnaire | None: ...

    def current_of_family(self, family_id: str) -> Questionnaire | None: ...

    def list_current(self, owner_ids: Iterable[str], shared_owner_ids: Iterable[str] = ()) -> tuple[Questionnaire, ...]:
        """Vigentes de owner_ids y los compartidos por shared_owner_ids."""
        ...

    def is_used(self, questionnaire_id: str) -> bool:
        """Si alguna sesión aplicó esta versión."""
        ...


class QuestionnaireResponseRepository(Interface):
    """Las respuestas se cifran antes de llegar a la base."""

    def add(self, response: QuestionnaireResponse) -> QuestionnaireResponse: ...

    def get(self, session_id: str, moment: str) -> QuestionnaireResponse | None: ...

    def list_for_session(self, session_id: str) -> tuple[QuestionnaireResponse, ...]: ...
