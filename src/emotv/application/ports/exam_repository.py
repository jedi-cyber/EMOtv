from __future__ import annotations

from typing import Protocol

from emotv.domain.exam import Exam
from emotv.domain.session import EmotionalSession


class ExamRepository(Protocol):
    """Puerto de persistencia de los exámenes simulados."""

    def save(self, exam: Exam) -> Exam: ...

    def get(self, exam_id: str) -> Exam | None: ...

    def get_by_join_code(self, join_code: str) -> Exam | None: ...

    def join_code_exists(self, join_code: str) -> bool: ...

    def list_by_owner(self, owner_user_id: str) -> tuple[Exam, ...]: ...

    def list_sessions(self, exam_id: str) -> tuple[EmotionalSession, ...]: ...
