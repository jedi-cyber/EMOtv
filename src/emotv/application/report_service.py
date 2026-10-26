"""Reporte de una sesión: lo redacta quien la condujo y lo revisa su docente
asignado.

Estados: borrador, enviado a revisión, con observaciones y aprobado. Si quien
condujo es un docente, al cerrar el reporte queda aprobado sin revisión. Un
reporte aprobado no se edita: se crea una versión nueva que vuelve a revisión.
Todo acceso pasa por can_access_session y queda en la auditoría. El texto y
los comentarios se guardan cifrados.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.authorization_service import AuthorizationService
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.report import (
    EDITABLE,
    ESTIMATES_NOTICE,
    ReportAction,
    ReportComment,
    ReportEvent,
    ReportSection,
    ReportStatus,
    SessionReport,
)
from emotv.domain.role import Role
from emotv.domain.session import EmotionalSession
from emotv.domain.session_state import SessionState
from emotv.domain.user import User

RESOURCE = "session_report"


class ReportNotFound(LookupError):
    pass


class ReportConflict(Exception):
    """La acción no corresponde al estado del reporte."""


class ReportService:
    def __init__(
        self,
        repository,                                   # PostgresReportRepository
        sessions,                                     # SessionService
        authorization: AuthorizationService,
        docente_of: Callable[[str], str | None],
        insights,                                     # SessionInsightsService
        audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.sessions = sessions
        self.authorization = authorization
        self.docente_of = docente_of
        self.insights = insights
        self.audit = audit
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Acceso -----------------------------------------------------------------------

    def _session(self, user: User, session_id: str) -> EmotionalSession:
        session = self.sessions.get_session(session_id)
        if session is None or session.owner_user_id is None:
            raise ReportNotFound(session_id)
        if not self.authorization.can_access_session(user, session):
            self.audit.record(user, AuditAction.VIEW, RESOURCE, session.id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a este reporte")
        return session

    def _report(self, user: User, report_id: str) -> tuple[SessionReport, EmotionalSession]:
        report = self.repository.get(report_id)
        if report is None:
            raise ReportNotFound(report_id)
        return report, self._session(user, report.session_id)

    def _event(self, report: SessionReport, action: ReportAction, user: User) -> ReportEvent:
        return ReportEvent(id=str(uuid4()), report_id=report.id, action=action, actor_user_id=user.id,
                           occurred_at=self.clock())

    def reviewer_of(self, report: SessionReport) -> str | None:
        """El docente asignado a quien redactó; un docente no necesita revisión."""
        return self.docente_of(report.author_user_id)

    def _require_author(self, user: User, report: SessionReport) -> None:
        if report.author_user_id != user.id:
            raise PermissionError("Solo quien condujo la sesión redacta su reporte")

    def _require_reviewer(self, user: User, report: SessionReport) -> None:
        if user.role is not Role.PSYCHOLOGIST or self.reviewer_of(report) != user.id:
            raise PermissionError("Solo el docente asignado revisa este reporte")

    @staticmethod
    def _require_current(report: SessionReport) -> None:
        if not report.current:
            raise ReportConflict("Esta versión ya fue reemplazada")

    # --- Redacción y revisión ---------------------------------------------------------------

    def create(self, user: User, session_id: str) -> SessionReport:
        session = self._session(user, session_id)
        if session.owner_user_id != user.id:
            raise PermissionError("Solo quien condujo la sesión redacta su reporte")
        if session.state not in (SessionState.COMPLETED, SessionState.CANCELLED):
            raise ReportConflict("El reporte se redacta cuando la sesión terminó")
        if self.repository.list_for_session(session.id):
            raise ReportConflict("La sesión ya tiene un reporte")
        now = self.clock()
        report_id = str(uuid4())
        report = SessionReport(id=report_id, family_id=report_id, version=1, session_id=session.id,
                               author_user_id=user.id, status=ReportStatus.DRAFT,
                               narrative="", created_at=now, updated_at=now)
        self.repository.save(report, self._event(report, ReportAction.CREATED, user))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, report.id)
        return report

    def edit(self, user: User, report_id: str, narrative: str) -> SessionReport:
        report, _ = self._report(user, report_id)
        self._require_author(user, report)
        self._require_current(report)
        if report.status is ReportStatus.APPROVED:
            raise ReportConflict("Un reporte aprobado no se edita: crea una versión nueva")
        if report.status not in EDITABLE:
            raise ReportConflict("El reporte está en revisión")
        updated = replace(report, narrative=narrative, updated_at=self.clock())
        self.repository.save(updated, self._event(updated, ReportAction.EDITED, user))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, report.id)
        return updated

    def submit(self, user: User, report_id: str) -> SessionReport:
        """Envía a revisión; si quien condujo es docente, el reporte queda aprobado."""
        report, _ = self._report(user, report_id)
        self._require_author(user, report)
        self._require_current(report)
        if report.status not in EDITABLE:
            raise ReportConflict("El reporte ya fue enviado")
        if not report.narrative:
            raise ValueError("Escribe el texto del reporte antes de enviarlo")
        now = self.clock()
        if user.role is Role.PSYCHOLOGIST:
            updated = replace(report, status=ReportStatus.APPROVED, approved_at=now, approved_by_user_id=user.id,
                              updated_at=now)
            self.repository.save(updated, self._event(updated, ReportAction.CLOSED, user))
            self.audit.record(user, AuditAction.APPROVE, RESOURCE, report.id)
            return updated
        if self.reviewer_of(report) is None:
            raise ReportConflict("No tienes un docente asignado que revise el reporte")
        updated = replace(report, status=ReportStatus.SUBMITTED, updated_at=now)
        self.repository.save(updated, self._event(updated, ReportAction.SUBMITTED, user))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, report.id)
        return updated

    def comment(self, user: User, report_id: str, section: ReportSection | str, text: str) -> ReportComment:
        report, _ = self._report(user, report_id)
        self._require_reviewer(user, report)
        if report.status is not ReportStatus.SUBMITTED:
            raise ReportConflict("Se comenta un reporte enviado a revisión")
        comment = ReportComment(id=str(uuid4()), report_id=report.id, section=section, text=text,
                                author_user_id=user.id, created_at=self.clock())
        self.repository.add_comment(comment, self._event(report, ReportAction.COMMENTED, user))
        self.audit.record(user, AuditAction.CREATE, "report_comment", comment.id)
        return comment

    def _review(self, user: User, report_id: str, approve: bool) -> SessionReport:
        report, _ = self._report(user, report_id)
        self._require_reviewer(user, report)
        if report.status is not ReportStatus.SUBMITTED:
            raise ReportConflict("Solo se revisa un reporte enviado a revisión")
        now = self.clock()
        if approve:
            updated = replace(report, status=ReportStatus.APPROVED, approved_at=now, approved_by_user_id=user.id,
                              updated_at=now)
            self.repository.save(updated, self._event(updated, ReportAction.APPROVED, user))
            self.audit.record(user, AuditAction.APPROVE, RESOURCE, report.id)
        else:
            updated = replace(report, status=ReportStatus.CHANGES_REQUESTED, updated_at=now)
            self.repository.save(updated, self._event(updated, ReportAction.RETURNED, user))
            self.audit.record(user, AuditAction.UPDATE, RESOURCE, report.id)
        return updated

    def approve(self, user: User, report_id: str) -> SessionReport:
        return self._review(user, report_id, approve=True)

    def return_with_comments(self, user: User, report_id: str) -> SessionReport:
        return self._review(user, report_id, approve=False)

    def new_version(self, user: User, report_id: str) -> SessionReport:
        """Para corregir un reporte aprobado: copia el texto y vuelve a borrador."""
        report, _ = self._report(user, report_id)
        self._require_author(user, report)
        self._require_current(report)
        if report.status is not ReportStatus.APPROVED:
            raise ReportConflict("Solo un reporte aprobado necesita una versión nueva; este se puede editar")
        now = self.clock()
        version = SessionReport(id=str(uuid4()), family_id=report.family_id, version=report.version + 1,
                                session_id=report.session_id, author_user_id=report.author_user_id, status=ReportStatus.DRAFT,
                                narrative=report.narrative, created_at=now, updated_at=now)
        self.repository.add_version(replace(report, superseded_at=now), version,
                                    self._event(version, ReportAction.NEW_VERSION, user))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, version.id)
        return version

    # --- Consulta e impresión -----------------------------------------------------------

    def _view(self, user: User, report: SessionReport, session: EmotionalSession,
              *, printing: bool = False) -> dict[str, Any]:
        versions = self.repository.list_for_session(session.id)
        metrics = self.insights.session_metrics(session)
        data: dict[str, Any] = {
            "id": report.id, "version": report.version, "status": report.status.value,
            "current": report.current, "narrative": report.narrative,
            "created_at": report.created_at.isoformat(), "updated_at": report.updated_at.isoformat(),
            "approved_at": report.approved_at.isoformat() if report.approved_at else None,
            "session": {"id": session.id, "code": session.code, "started_at": session.started_at.isoformat(),
                        "session_type": session.session_type.value,
                        "emotion_model_id": session.emotion_model_id,
                        "emotion_model_version": session.emotion_model_version},
            # Solo el código de la sesión: el sistema no registra a la persona.
            "session_code": session.code,
            "estimates_notice": ESTIMATES_NOTICE,
            "abstract_notice": metrics.get("abstract_notice"),
            "timeline": self.insights.session_timeline(session),
            "metrics": metrics,
        }
        if printing:
            return data
        reviewer = self.reviewer_of(report)
        is_author = report.author_user_id == user.id
        data.update({
            "authored_by_me": is_author,
            "requires_review": reviewer is not None,
            "can_edit": is_author and report.current and report.status in EDITABLE,
            "can_review": (user.role is Role.PSYCHOLOGIST and reviewer == user.id and report.current
                           and report.status is ReportStatus.SUBMITTED),
            "can_new_version": is_author and report.current and report.status is ReportStatus.APPROVED,
            "comments": [{"id": item.id, "section": item.section.value, "text": item.text,
                          "created_at": item.created_at.isoformat()} for item in self.repository.list_comments(report.id)],
            "history": [{"action": item.action.value, "occurred_at": item.occurred_at.isoformat(), "version": next(
                (version.version for version in versions if version.id == item.report_id), None),
                "by": "author" if item.actor_user_id == report.author_user_id else "docente"}
                for item in self.repository.list_events(tuple(version.id for version in versions))],
            "versions": [{"id": item.id, "version": item.version, "status": item.status.value} for item in versions],
        })
        return data

    def for_session(self, user: User, session_id: str) -> dict[str, Any]:
        """El reporte vigente de la sesión."""
        session = self._session(user, session_id)
        versions = self.repository.list_for_session(session.id)
        if not versions:
            self.audit.record(user, AuditAction.VIEW, RESOURCE, session.id)
            raise ReportNotFound(session_id)
        report = next((item for item in versions if item.current), versions[-1])
        self.audit.record(user, AuditAction.VIEW, RESOURCE, report.id)
        return self._view(user, report, session)

    def get(self, user: User, report_id: str) -> dict[str, Any]:
        report, session = self._report(user, report_id)
        self.audit.record(user, AuditAction.VIEW, RESOURCE, report.id)
        return self._view(user, report, session)

    def print_view(self, user: User, report_id: str) -> dict[str, Any]:
        """Vista imprimible del reporte aprobado; cada impresión queda en la auditoría.
        No se genera ningún archivo en el servidor: imprime el navegador."""
        report, session = self._report(user, report_id)
        if report.status is not ReportStatus.APPROVED:
            raise ReportConflict("Solo se imprime un reporte aprobado")
        self.repository.add_event(self._event(report, ReportAction.PRINTED, user))
        self.audit.record(user, AuditAction.PRINT, RESOURCE, report.id)
        return self._view(user, report, session, printing=True)
