"""Por revisar del docente: lo que su grupo dejó esperando su revisión.

El docente supervisa sin estar presente en cada sesión: los usuarios conducen y
el docente revisa después, cuando tiene tiempo, los reportes enviados y los
pedidos de eliminación. Solo lista sesiones a las que ya tiene acceso; no
expone el texto de los reportes."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from emotv.application import AuthenticationService
from emotv.application.audit_service import AuditService
from emotv.application.ports import StudentRepository, UserRepository
from emotv.application.report_service import ReportService
from emotv.domain import EmotionalSession, Role, User
from emotv.domain.audit import AuditAction
from emotv.interfaces.web.auth_router import create_current_user_dependency


def create_review_router(
    visible_sessions: Callable[[User], list[EmotionalSession]] | None,
    reports: ReportService | None,
    students: StudentRepository | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    audit: AuditService | None = None,
) -> APIRouter:
    router = APIRouter(tags=["reviews"])
    current_user = create_current_user_dependency(authentication, users)

    def pending(user: User) -> list[dict[str, Any]]:
        if user.role is not Role.PSYCHOLOGIST:
            raise HTTPException(status_code=403, detail="Solo el docente revisa lo que envía su grupo")
        if visible_sessions is None or students is None:
            raise HTTPException(status_code=503, detail="Las sesiones no están configuradas")
        # Las sesiones propias del docente son de demostración: no esperan revisión.
        group = [item for item in visible_sessions(user) if item.owner_user_id != user.id]

        def entry(kind: str, session: EmotionalSession, since: datetime, report_id: str | None) -> dict[str, Any]:
            student = students.get_by_id(session.student_id) if session.student_id else None
            return {"kind": kind, "session_id": session.id, "session_code": session.code,
                    "user_code": student.student_code if student else None,
                    "waiting_since": since.isoformat(), "report_id": report_id}

        items: list[dict[str, Any]] = []
        if reports is not None:
            waiting = reports.pending_review(user, tuple(item.id for item in group))
            current = reports.current_for_sessions(tuple(waiting))
            items += [entry("report", session, current[session.id].updated_at, current[session.id].id)
                      for session in group if session.id in waiting]
        items += [entry("deletion", session, session.deletion_requested_at, None)
                  for session in group if session.deletion_requested_at is not None]
        # Lo que más tiempo lleva esperando va primero.
        return sorted(items, key=lambda item: item["waiting_since"])

    @router.get("/reviews")
    def list_reviews(user: User = Depends(current_user)) -> list[dict[str, Any]]:
        items = pending(user)
        if audit is not None:
            audit.record(user, AuditAction.VIEW, "reviews", None)
        return items

    @router.get("/reviews/count")
    def count_reviews(user: User = Depends(current_user)) -> dict[str, int]:
        """Para el contador del menú: solo el número, sin auditar cada consulta."""
        return {"pending": len(pending(user))}

    return router
