"""Estadísticas agregadas de sesiones.

Cuentan sesiones, no personas: no hay seguimiento ni totales por persona
evaluada. Solo describen lo registrado (expresiones estimadas y respuestas tal
como se dieron); no suman, no calculan puntajes y no interpretan. Todo se
calcula en el servidor con las sesiones a las que la cuenta ya tiene acceso
(can_access_session) y cada consulta se audita, sin contenido.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from emotv.application.audit_service import AuditService
from emotv.application.authorization_service import AuthorizationService
from emotv.application.session_insights_service import SessionInsightsService
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.expression_info import EXPRESSION_KEYS
from emotv.domain.guided_session import CaptureQuality
from emotv.domain.questionnaire import FACES, QuestionKind
from emotv.domain.role import Role
from emotv.domain.session import EmotionalSession
from emotv.domain.session_state import SessionState
from emotv.domain.user import User

RESOURCE = "session_statistics"
FEW_SESSIONS = 5
NOTICE = ("Estas estadísticas cuentan sesiones, no personas, y son estimaciones. No permiten sacar conclusiones "
          "sobre ninguna persona.")
FEW_SESSIONS_NOTICE = "Hay pocas sesiones para sacar conclusiones."
NO_PROTOCOL = "none"
Scope = Literal["mine", "group"]


@dataclass(frozen=True, slots=True)
class StatisticsFilter:
    scope: Scope = "mine"
    date_from: date | None = None
    date_to: date | None = None
    # Familia del protocolo (todas sus versiones) o "none": sesiones sin protocolo.
    protocol: str | None = None
    # propia, adulto o infantil.
    audience: str | None = None
    questionnaire_id: str | None = None


def _percent(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


class SessionStatisticsService:
    def __init__(
        self,
        sessions,                                       # SessionService
        insights: SessionInsightsService,
        authorization: AuthorizationService,
        actor_student_id: Callable[[User], str | None],
        group_user_ids: Callable[[str], Iterable[str]],
        email_of: Callable[[str], str | None],
        audit: AuditService,
    ) -> None:
        self.sessions = sessions
        self.insights = insights
        self.authorization = authorization
        self.actor_student_id = actor_student_id
        self.group_user_ids = group_user_ids
        self.email_of = email_of
        self.audit = audit

    # --- Sesiones visibles ------------------------------------------------------------

    def _owners(self, user: User, scope: Scope) -> tuple[str, ...]:
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            raise PermissionError("Las estadísticas son para usuarios y docentes")
        if scope == "group":
            if user.role is not Role.PSYCHOLOGIST:
                raise PermissionError("Solo el docente ve las estadísticas de su grupo")
            return tuple(self.group_user_ids(user.id))
        if scope != "mine":
            raise ValueError("Elige «Mis sesiones» o «Mi grupo»")
        return (user.id,)

    def _family(self, session: EmotionalSession) -> str | None:
        protocol = self.insights.protocols(session.protocol_id) if session.protocol_id else None
        return protocol.family_id if protocol else None

    def _matches(self, session: EmotionalSession, filters: StatisticsFilter) -> bool:
        day = session.started_at.date()
        if filters.date_from and day < filters.date_from:
            return False
        if filters.date_to and day > filters.date_to:
            return False
        if filters.audience and session.session_type.value != filters.audience:
            return False
        if filters.protocol == NO_PROTOCOL:
            return session.protocol_id is None
        return not filters.protocol or self._family(session) == filters.protocol

    # --- Consulta -----------------------------------------------------------------------

    def statistics(self, user: User, filters: StatisticsFilter) -> dict[str, Any]:
        try:
            owners = self._owners(user, filters.scope)
        except PermissionError:
            self.audit.record(user, AuditAction.VIEW, RESOURCE, filters.scope, AuditResult.DENIED)
            raise
        actor = self.actor_student_id(user)
        # Solo las sesiones a las que la cuenta ya tiene acceso.
        in_scope = [session for owner in owners for session in self.sessions.list_sessions_by_owner(owner)
                    if self.authorization.can_access_session(user, session, actor_student_id=actor)]
        selected = [session for session in in_scope if self._matches(session, filters)]
        self.audit.record(user, AuditAction.VIEW, RESOURCE, filters.scope)
        result = {
            "scope": filters.scope,
            "notice": NOTICE,
            "few_sessions": len(selected) < FEW_SESSIONS,
            "few_sessions_notice": FEW_SESSIONS_NOTICE if len(selected) < FEW_SESSIONS else None,
            "sessions": self._summary(selected),
            "expressions": self._expressions(selected),
            "coincidence": self._coincidence(selected),
            "protocols": self._protocol_options(in_scope),
            **self._questionnaires(selected, filters.questionnaire_id),
        }
        if filters.scope == "group":
            result["by_user"] = self._by_user(selected, owners)
        return result

    @staticmethod
    def _summary(sessions: list[EmotionalSession]) -> dict[str, Any]:
        completed = [item for item in sessions if item.state is SessionState.COMPLETED]
        durations = [(item.completed_at - item.started_at).total_seconds() for item in completed if item.completed_at]
        return {
            "total": len(sessions),
            "completed": len(completed),
            # Canceladas o detenidas (alguien pidió parar).
            "interrupted": sum(1 for item in sessions if item.state is SessionState.CANCELLED),
            "average_duration_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        }

    def _expressions(self, sessions: list[EmotionalSession]) -> dict[str, Any]:
        """Porcentaje de las capturas de buena calidad estimadas en cada expresión."""
        captures: Counter[str] = Counter()
        in_sessions: dict[str, set[str]] = {key: set() for key in EXPRESSION_KEYS}
        excluded = 0
        for session in sessions:
            for item in self.insights.guided.list_captures(session.id):
                if item.quality is not CaptureQuality.GOOD or item.emotion not in EXPRESSION_KEYS:
                    excluded += 1
                    continue
                captures[item.emotion] += 1
                in_sessions[item.emotion].add(session.id)
        counted = sum(captures.values())
        return {
            "counted_captures": counted,
            "excluded_captures": excluded,
            "rows": [{"expression": key, "captures": captures[key], "percent": _percent(captures[key], counted),
                      "sessions": len(in_sessions[key])} for key in EXPRESSION_KEYS],
        }

    def _coincidence(self, sessions: list[EmotionalSession]) -> dict[str, int]:
        """Estímulos emocionales: la primera captura de buena calidad de cada uno
        decide si la expresión estimada coincidió con la esperada (como en la
        métrica de cada sesión)."""
        compared = matched = 0
        for session in sessions:
            if session.protocol_id is None:
                continue
            totals = self.insights.session_metrics(session)["totals"]
            compared += totals["counted"]
            matched += totals["matched"]
        return {"compared": compared, "matched": matched}

    def _protocol_options(self, sessions: list[EmotionalSession]) -> list[dict[str, str]]:
        names: dict[str, tuple[int, str]] = {}
        for session in sessions:
            protocol = self.insights.protocols(session.protocol_id) if session.protocol_id else None
            if protocol and protocol.version >= names.get(protocol.family_id, (0, ""))[0]:
                names[protocol.family_id] = (protocol.version, protocol.name)
        return sorted(({"family_id": family, "name": name} for family, (_, name) in names.items()),
                      key=lambda item: item["name"].lower())

    def _by_user(self, sessions: list[EmotionalSession], owners: tuple[str, ...]) -> list[dict[str, Any]]:
        """Totales por usuario del grupo (por correo); nada más de cada sesión."""
        rows = []
        for owner in owners:
            own = [item for item in sessions if item.owner_user_id == owner]
            rows.append({"email": self.email_of(owner) or "Cuenta eliminada", "sessions": len(own),
                         "completed": sum(1 for item in own if item.state is SessionState.COMPLETED),
                         "interrupted": sum(1 for item in own if item.state is SessionState.CANCELLED)})
        return sorted(rows, key=lambda row: row["email"])

    def _questionnaires(self, sessions: list[EmotionalSession], chosen: str | None) -> dict[str, Any]:
        """Distribución de respuestas por pregunta para una versión elegida. Se
        cuenta cuántas veces se eligió cada opción o punto; no se suma ni se
        interpreta. Las respuestas de texto no se muestran: solo cuántas hubo."""
        source = self.insights.questionnaire_responses
        if source is None:
            return {"questionnaires": [], "questionnaire": None}
        responses = [response for session in sessions for response in source(session.id)]
        counts = Counter(response.questionnaire_id for response in responses)
        options = []
        for questionnaire_id, total in counts.items():
            questionnaire = self.insights.questionnaires(questionnaire_id)
            if questionnaire is not None:
                options.append({"id": questionnaire.id, "title": questionnaire.title,
                                "version": questionnaire.version, "responses": total})
        options.sort(key=lambda item: (item["title"].lower(), item["version"]))
        questionnaire = self.insights.questionnaires(chosen) if chosen in counts else None
        if questionnaire is None:
            return {"questionnaires": options, "questionnaire": None}
        chosen_responses = [response for response in responses if response.questionnaire_id == questionnaire.id]
        questions = []
        for question in questionnaire.questions:
            answers = [response.answers.get(question.id) for response in chosen_responses]
            given = [answer for answer in answers if answer not in (None, "", [])]
            row: dict[str, Any] = {"text": question.text, "kind": question.kind.value, "answered": len(given),
                                   "unanswered": len(answers) - len(given), "counts": None}
            if question.kind in (QuestionKind.SCALE, QuestionKind.FACES):
                top = question.scale_points if question.kind is QuestionKind.SCALE else FACES
                tally = Counter(given)
                row["counts"] = [{"label": str(point), "count": tally[point]} for point in range(1, top + 1)]
                row["min_label"], row["max_label"] = question.min_label, question.max_label
            elif question.kind is QuestionKind.SINGLE_CHOICE:
                tally = Counter(given)
                row["counts"] = [{"label": option, "count": tally[option]} for option in question.options]
            elif question.kind is QuestionKind.MULTIPLE_CHOICE:
                tally = Counter(option for answer in given for option in answer)
                row["counts"] = [{"label": option, "count": tally[option]} for option in question.options]
            # Texto breve: solo cuántas respuestas hubo, nunca su contenido.
            questions.append(row)
        return {"questionnaires": options, "questionnaire": {
            "id": questionnaire.id, "title": questionnaire.title, "version": questionnaire.version,
            "responses": len(chosen_responses), "questions": questions}}
