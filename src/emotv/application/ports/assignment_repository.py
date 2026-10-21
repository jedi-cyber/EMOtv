from __future__ import annotations

from typing import Protocol

from emotv.domain.psychologist_assignment import PsychologistAssignment


class AssignmentRepository(Protocol):
    """Grupo de cada docente: un usuario pertenece a un solo docente."""

    def assign(self, assignment: PsychologistAssignment) -> PsychologistAssignment:
        """Asigna el usuario al docente; si ya pertenecía a otro, lo mueve.
        Si la asignación ya existe, la devuelve sin cambiarla."""
        ...

    def get_by_student(self, student_id: str) -> PsychologistAssignment | None:
        """Asignación vigente del usuario, o None si no tiene docente."""
        ...

    def unassign(self, psychologist_user_id: str, student_id: str) -> bool:
        """Elimina la asignación; devuelve False si no existía."""
        ...

    def is_assigned(self, psychologist_user_id: str, student_id: str) -> bool: ...

    def list_by_psychologist(self, psychologist_user_id: str) -> tuple[PsychologistAssignment, ...]: ...
