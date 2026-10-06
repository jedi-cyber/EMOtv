from __future__ import annotations

from emotv.domain.psychologist_assignment import PsychologistAssignment


class InMemoryAssignmentRepository:
    """Asignaciones en memoria para pruebas."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], PsychologistAssignment] = {}

    def assign(self, assignment: PsychologistAssignment) -> PsychologistAssignment:
        key = (assignment.psychologist_user_id, assignment.student_id)
        return self._items.setdefault(key, assignment)

    def unassign(self, psychologist_user_id: str, student_id: str) -> bool:
        return self._items.pop((psychologist_user_id, student_id), None) is not None

    def is_assigned(self, psychologist_user_id: str, student_id: str) -> bool:
        return (psychologist_user_id, student_id) in self._items

    def list_by_psychologist(self, psychologist_user_id: str) -> tuple[PsychologistAssignment, ...]:
        return tuple(sorted((item for (owner, _), item in self._items.items() if owner == psychologist_user_id),
                            key=lambda item: (item.assigned_at, item.student_id)))
