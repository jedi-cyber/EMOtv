"""Línea de tiempo, métricas por estímulo y tendencias del participante.

Las ven quien condujo la sesión y su docente: con participante, por
can_access_participant; en una sesión propia, por can_access_session. Cada
consulta, también las denegadas, queda en la auditoría. El sistema describe; no
interpreta.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from emotv.application.audit_service import AuditService
from emotv.application.authorization_service import AuthorizationService
from emotv.application.session_metrics import SessionPoint, stimulus_metrics, trend
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.guided_session import GuidedPhase
from emotv.domain.participant import Participant
from emotv.domain.protocol import Protocol
from emotv.domain.session import EmotionalSession
from emotv.domain.stimulus import Stimulus
from emotv.domain.user import User

TIMELINE = "session_timeline"
METRICS = "session_metrics"
TRENDS = "participant_trends"


class InsightsNotFound(LookupError):
    pass


class SessionInsightsService:
    def __init__(
        self,
        sessions,                                     # SessionService
        guided,                                       # repositorio de la sesión guiada
        protocols: Callable[[str], Protocol | None],
        stimuli: Callable[[str], Stimulus | None],
        participants: Callable[[str], Participant | None],
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
        self.participants = participants
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
        if session.participant_id is not None:
            allowed = self.authorization.can_access_participant(user, self.participants(session.participant_id))
        else:
            allowed = self.authorization.can_access_session(user, session, actor_student_id=self.actor_student_id(user))
        if not allowed:
            self.audit.record(user, AuditAction.VIEW, resource, session.id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a esta sesión")
        self.audit.record(user, AuditAction.VIEW, resource, session.id)
        return session

    # --- Métricas -------------------------------------------------------------------------

    def _session_metrics(self, session: EmotionalSession) -> dict[str, Any]:
        protocol = self.protocols(session.protocol_id) if session.protocol_id else None
        if protocol is None:
            return stimulus_metrics((), {}, ())
        stimuli = {step.stimulus_id: self.stimuli(step.stimulus_id) for step in protocol.steps}
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
                stimulus = self.stimuli(step.stimulus_id)
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

    # --- Tendencias del participante ------------------------------------------------------

    def trends(self, user: User, participant_id: str) -> dict[str, Any]:
        participant = self.participants(participant_id)
        if participant is None:
            raise InsightsNotFound(participant_id)
        if not self.authorization.can_access_participant(user, participant):
            self.audit.record(user, AuditAction.VIEW, TRENDS, participant.id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a este participante")
        self.audit.record(user, AuditAction.VIEW, TRENDS, participant.id)
        groups: dict[str, dict[str, Any]] = {}
        for session in self.sessions.list_sessions_by_participant(participant.id):
            protocol = self.protocols(session.protocol_id) if session.protocol_id else None
            if protocol is None:
                continue
            # Las versiones de un mismo protocolo se comparan entre sí.
            group = groups.setdefault(protocol.family_id, {"protocol_name": protocol.name, "points": []})
            group["protocol_name"] = protocol.name
            totals = self._session_metrics(session)["totals"]
            group["points"].append(SessionPoint(session.id, session.started_at.isoformat(), protocol.version,
                                                totals["matched"], totals["counted"]))
        return {
            "participant_id": participant.id,
            "code": participant.code,
            "protocols": [{"protocol_family_id": family, "protocol_name": data["protocol_name"], **trend(data["points"])}
                          for family, data in groups.items()],
        }
