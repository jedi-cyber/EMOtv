from __future__ import annotations

from typing import Protocol

from emotv.domain.psychologist_assignment import PsychologistAssignment


class AssignmentRepository(Protocol):
    """Estudiantes que cada psicólogo está autorizado a consultar."""

    def assign(self, assignment: PsychologistAssignment) -> PsychologistAssignment:
        """Crea la asignación; si ya existe, devuelve la existente sin cambiarla."""
        ...

    def unassign(self, psychologist_user_id: str, student_id: str) -> bool:
        """Elimina la asignación; devuelve False si no existía."""
        ...

    def is_assigned(self, psychologist_user_id: str, student_id: str) -> bool: ...

    def list_by_psychologist(self, psychologist_user_id: str) -> tuple[PsychologistAssignment, ...]: ...
