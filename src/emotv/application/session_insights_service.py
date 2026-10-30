"""Línea de tiempo y métricas por estímulo de una sesión.

Las ven quien condujo la sesión y su docente (can_access_session). Cada
consulta, también las denegadas, queda en la auditoría. El sistema describe; no
interpreta. No hay tendencias por persona: no se registra a nadie.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from emotv.application.audit_service import AuditService
from emotv.application.authorization_service import AuthorizationService
from emotv.application.session_metrics import stimulus_metrics
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.guided_session import GuidedPhase
from emotv.domain.protocol import Protocol
from emotv.domain.session import EmotionalSession
from emotv.domain.stimulus import Stimulus
from emotv.domain.user import User

TIMELINE = "session_timeline"
METRICS = "session_metrics"


class InsightsNotFound(LookupError):
    pass


class SessionInsightsService:
    def __init__(
        self,
        sessions,                                     # SessionService
        guided,                                       # repositorio de la sesión guiada
        protocols: Callable[[str], Protocol | None],
        stimuli: Callable[[str], Stimulus | None],
        questionnaire_responses: Callable[[str], tuple] | None,
        questionnaires: Callable[[str], Any],
        authorization: AuthorizationService,
        actor_student_id: Callable[[User], str | None],
        audit: AuditService,
    ) -> None:
        self.sessions = sessions
        self.guided = guided
        self.protocols = protocols
        self.stimuli = stimuli
        self.questionnaire_responses = questionnaire_responses
        self.questionnaires = questionnaires
        self.authorization = authorization
        self.actor_student_id = actor_student_id
        self.audit = audit

    # --- Acceso -----------------------------------------------------------------------

    def _allowed_session(self, user: User, session_id: str, resource: str) -> EmotionalSession:
        session = self.sessions.get_session(session_id)
        if session is None:
            raise InsightsNotFound(session_id)
        if not self.authorization.can_access_session(user, session, actor_student_id=self.actor_student_id(user)):
            self.audit.record(user, AuditAction.VIEW, resource, session.id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a esta sesión")
        self.audit.record(user, AuditAction.VIEW, resource, session.id)
        return session

    # --- Métricas -------------------------------------------------------------------------

    def _session_metrics(self, session: EmotionalSession) -> dict[str, Any]:
        protocol = self.protocols(session.protocol_id) if session.protocol_id else None
        if protocol is None:
            return stimulus_metrics((), {}, ())
        stimuli = {step.stimulus_id: self.stimuli(step.stimulus_id) if step.stimulus_id else None
                   for step in protocol.steps}
        run = self.guided.get_run(session.id)
        skipped = [item["step_index"] for item in run.steps_log if item.get("skipped")] if run else []
        return stimulus_metrics(protocol.steps, stimuli, self.guided.list_captures(session.id),
                                self.guided.list_verbal(session.id), skipped)

    def metrics(self, user: User, session_id: str) -> dict[str, Any]:
        return self.session_metrics(self._allowed_session(user, session_id, METRICS))

    # --- Línea de tiempo -----------------------------------------------------------------

    def timeline(self, user: User, session_id: str) -> dict[str, Any]:
        """Un solo eje de tiempo, en segundos desde el inicio de la sesión."""
        return self.session_timeline(self._allowed_session(user, session_id, TIMELINE))

    def session_metrics(self, session: EmotionalSession) -> dict[str, Any]:
        """Sin control de acceso ni auditoría: lo usa quien ya los aplicó (el reporte)."""
        return {"session_id": session.id, **self._session_metrics(session)}

    def session_timeline(self, session: EmotionalSession) -> dict[str, Any]:
        """Sin control de acceso ni auditoría: lo usa quien ya los aplicó (el reporte)."""
        start = session.started_at

        def at(moment: datetime | str | None) -> float | None:
            if moment is None:
                return None
            value = datetime.fromisoformat(moment) if isinstance(moment, str) else moment
            return round((value - start).total_seconds(), 2)

        protocol = self.protocols(session.protocol_id) if session.protocol_id else None
        titles = {}
        if protocol:
            for index, step in enumerate(protocol.steps):
                stimulus = self.stimuli(step.stimulus_id) if step.stimulus_id else None
                titles[index] = (stimulus.title if stimulus else "", stimulus.kind.value if stimulus else "")
        run = self.guided.get_run(session.id)
        stimuli_lane = []
        if run is not None:
            for item in run.steps_log:
                title, kind = titles.get(item["step_index"], ("", ""))
                stimuli_lane.append({"step_index": item["step_index"], "title": title, "kind": kind,
                                     "start": at(item.get("started_at")), "end": at(item.get("ended_at")),
                                     "skipped": bool(item.get("skipped"))})
            if run.phase in (GuidedPhase.BEFORE_ANALYZER, GuidedPhase.STIMULI) and run.step_started_at:
                title, kind = titles.get(run.step_index, ("", ""))
                stimuli_lane.append({"step_index": run.step_index, "title": title, "kind": kind,
                                     "start": at(run.step_started_at), "end": None, "skipped": False})
        questionnaires_lane = []
        for response in (self.questionnaire_responses(session.id) if self.questionnaire_responses else ()):
            questionnaire = self.questionnaires(response.questionnaire_id)
            questionnaires_lane.append({
                "time": at(response.submitted_at), "moment": response.moment.value,
                "title": questionnaire.title if questionnaire else "",
                # Las respuestas tal como se dieron, con el texto de cada pregunta.
                "answers": [{"question": question.text, "kind": question.kind.value,
                             "answer": response.answers.get(question.id)}
                            for question in (questionnaire.questions if questionnaire else ())],
            })
        captures_lane = [{"time": at(item.captured_at), "step_index": item.step_index, "emotion": item.emotion,
                          "probability": item.confidence, "quality": item.quality.value}
                         for item in self.guided.list_captures(session.id)]
        said_lane = [{"time": at(item.recorded_at), "step_index": item.step_index,
                      "title": titles.get(item.step_index, ("", ""))[0], "text": item.text}
                     for item in self.guided.list_verbal(session.id)]
        markers_lane = [{"time": at(item.occurred_at), "kind": item.kind.value, "note": item.note}
                        for item in self.guided.list_markers(session.id)]
        times = [value for value in (
            *(item["end"] or item["start"] for item in stimuli_lane),
            *(item["time"] for item in (*questionnaires_lane, *captures_lane, *said_lane, *markers_lane)),
            at(session.completed_at)) if value is not None]
        return {
            "session_id": session.id,
            "session_code": session.code,
            "started_at": start.isoformat(),
            "duration_seconds": max(times, default=0.0),
            "lanes": {
                "questionnaires": questionnaires_lane,
                "stimuli": stimuli_lane,
                "captures": captures_lane,
                "said": said_lane,
                "markers": markers_lane,
                # Reservado: el ritmo cardíaco se agregará cuando exista el sensor.
                "heart_rate": [],
            },
        }
