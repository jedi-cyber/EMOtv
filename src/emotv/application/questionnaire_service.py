"""Cuestionarios que crea quien conduce la sesión y sus respuestas.

EMOtv solo presenta el cuestionario y registra las respuestas tal como se
dieron: no lo valida como instrumento, no calcula puntajes ni interpreta
respuestas. Las respuestas se guardan cifradas, asociadas a la sesión y a la
versión exacta del cuestionario; las ven quien condujo la sesión y su docente
(can_access_session), nunca los administradores, y cada consulta se audita.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from emotv.application.audit_service import AuditService
from emotv.application.ports.questionnaire_repositories import (
    QuestionnaireRepository,
    QuestionnaireResponseRepository,
)
from emotv.domain.audit import AuditAction, AuditResult
from emotv.domain.questionnaire import (
    EntryMode,
    Question,
    QuestionKind,
    Questionnaire,
    QuestionnaireResponse,
    ResponseMoment,
)
from emotv.domain.role import Role
from emotv.domain.session import EmotionalSession
from emotv.domain.user import User

RESOURCE = "questionnaire"
RESPONSE = "questionnaire_response"
DocenteOf = Callable[[str], str | None]
SessionLookup = Callable[[str], EmotionalSession | None]
SessionAccess = Callable[[User, EmotionalSession], bool]

# Plantilla inicial editable: se copia a la cuenta y cada quien la modifica.
STARTER_TITLE = "¿Cómo llegas a la sesión?"
STARTER_INSTRUCTIONS = "Elige la figura que mejor muestre cómo estás ahora. No hay respuestas correctas."
STARTER_QUESTIONS = (
    Question(id="como-te-sientes", kind=QuestionKind.FACES, text="¿Cómo te sientes?", required=True),
    Question(id="tranquilo-inquieto", kind=QuestionKind.FACES, text="¿Qué tan tranquilo o inquieto estás?",
             required=True, min_label="Tranquilo", max_label="Inquieto"),
)


class QuestionnaireNotFound(LookupError):
    pass


class ResponsesUnavailable(RuntimeError):
    """Sin SENSITIVE_DATA_KEY no se guardan respuestas."""


class ResponseConflict(Exception):
    """La sesión no espera ese cuestionario o ya se respondió."""


@dataclass(frozen=True, slots=True)
class QuestionnaireDraft:
    title: str
    instructions: str
    questions: tuple[Question, ...]


class QuestionnaireService:
    def __init__(
        self,
        repository: QuestionnaireRepository,
        audit: AuditService,
        docente_of: DocenteOf,
        responses: QuestionnaireResponseRepository | None = None,
        sessions: SessionLookup | None = None,
        session_access: SessionAccess | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.audit = audit
        self.docente_of = docente_of
        self.responses = responses
        self.sessions = sessions
        self.session_access = session_access
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # --- Acceso a los cuestionarios -------------------------------------------

    @staticmethod
    def _require_conductor(user: User) -> None:
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            raise PermissionError("Los cuestionarios los crean y aplican quienes conducen sesiones")

    def _shared_by(self, user: User) -> tuple[str, ...]:
        """Docente cuyas plantillas compartidas ve la cuenta."""
        if user.role is Role.STUDENT:
            docente = self.docente_of(user.id)
            return (docente,) if docente else ()
        return ()

    def can_use(self, user: User, questionnaire: Questionnaire) -> bool:
        """Propios, o la plantilla que su docente comparte con el grupo."""
        if not user.is_active or user.role not in (Role.STUDENT, Role.PSYCHOLOGIST):
            return False
        if questionnaire.owner_user_id == user.id:
            return True
        return questionnaire.shared_with_group and questionnaire.owner_user_id in self._shared_by(user)

    def list_for(self, user: User) -> tuple[Questionnaire, ...]:
        self._require_conductor(user)
        return self.repository.list_current((user.id,), self._shared_by(user))

    def get(self, user: User, questionnaire_id: str) -> Questionnaire:
        questionnaire = self.repository.get(questionnaire_id)
        if questionnaire is None or not self.can_use(user, questionnaire):
            raise QuestionnaireNotFound(questionnaire_id)
        return questionnaire

    def is_used(self, questionnaire: Questionnaire) -> bool:
        return self.repository.is_used(questionnaire.id)

    def current_for(self, user: User, questionnaire_id: str) -> Questionnaire:
        """La versión vigente del cuestionario indicado, para aplicarla en una sesión."""
        questionnaire = self.get(user, questionnaire_id)
        if not questionnaire.current:
            questionnaire = self.repository.current_of_family(questionnaire.family_id) or questionnaire
            if not self.can_use(user, questionnaire):
                raise QuestionnaireNotFound(questionnaire_id)
        return questionnaire

    # --- Creación, versiones, plantillas ----------------------------------------

    def _new(self, user: User, draft: QuestionnaireDraft, copied_from_id: str | None = None) -> Questionnaire:
        family = str(uuid4())
        questionnaire = self.repository.add(Questionnaire(
            id=family, family_id=family, version=1, owner_user_id=user.id, title=draft.title,
            instructions=draft.instructions, created_at=self.clock(), questions=draft.questions,
            copied_from_id=copied_from_id))
        self.audit.record(user, AuditAction.CREATE, RESOURCE, questionnaire.id)
        return questionnaire

    def create(self, user: User, draft: QuestionnaireDraft) -> Questionnaire:
        self._require_conductor(user)
        return self._new(user, draft)

    def create_starter(self, user: User) -> Questionnaire:
        """Copia la plantilla inicial (dos preguntas de caritas) a la cuenta."""
        self._require_conductor(user)
        return self._new(user, QuestionnaireDraft(STARTER_TITLE, STARTER_INSTRUCTIONS, STARTER_QUESTIONS))

    def copy(self, user: User, questionnaire_id: str) -> Questionnaire:
        """Copia propia y editable de un cuestionario propio o de una plantilla del docente."""
        self._require_conductor(user)
        source = self.get(user, questionnaire_id)
        return self._new(user, QuestionnaireDraft(source.title, source.instructions, source.questions),
                         copied_from_id=source.id)

    def edit(self, user: User, questionnaire_id: str, draft: QuestionnaireDraft) -> Questionnaire:
        """Una versión sin usar se reemplaza; una usada en una sesión no se toca y
        se crea la siguiente."""
        self._require_conductor(user)
        current = self.get(user, questionnaire_id)
        if current.owner_user_id != user.id:
            raise PermissionError("Solo su autor edita el cuestionario; puedes copiarlo y modificar la copia")
        if not current.current:
            raise ValueError("Esta versión ya fue reemplazada: edita la versión vigente")
        fields = dict(title=draft.title, instructions=draft.instructions, questions=draft.questions)
        if self.repository.is_used(current.id):
            now = self.clock()
            updated = self.repository.add_version(current.id, now, replace(
                current, id=str(uuid4()), version=current.version + 1, created_at=now, **fields))
        else:
            updated = self.repository.replace(replace(current, **fields))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, updated.id)
        return updated

    def share(self, user: User, questionnaire_id: str, shared: bool) -> Questionnaire:
        """El docente ofrece un cuestionario suyo como plantilla a su grupo."""
        if not user.is_active or user.role is not Role.PSYCHOLOGIST:
            raise PermissionError("Solo el docente comparte cuestionarios con su grupo")
        questionnaire = self.get(user, questionnaire_id)
        if questionnaire.owner_user_id != user.id or not questionnaire.current:
            raise PermissionError("Comparte la versión vigente de un cuestionario tuyo")
        if questionnaire.shared_with_group == shared:
            return questionnaire
        updated = self.repository.replace(replace(questionnaire, shared_with_group=shared))
        self.audit.record(user, AuditAction.UPDATE, RESOURCE, questionnaire.id)
        return updated

    # --- Respuestas en una sesión -----------------------------------------------

    def _response_store(self) -> QuestionnaireResponseRepository:
        if self.responses is None:
            raise ResponsesUnavailable("Las respuestas no se pueden guardar: falta la clave de cifrado de datos sensibles")
        return self.responses

    def _session(self, session_id: str) -> EmotionalSession:
        session = self.sessions(session_id) if self.sessions else None
        if session is None:
            raise QuestionnaireNotFound(session_id)
        return session

    @staticmethod
    def expected(session: EmotionalSession, moment: ResponseMoment) -> str | None:
        return session.pre_questionnaire_id if moment is ResponseMoment.PRE else session.post_questionnaire_id

    def pending_for(self, user: User, session_id: str, moment: ResponseMoment | str) -> Questionnaire:
        """El cuestionario que la sesión espera, para presentarlo a quien la conduce."""
        session = self._session(session_id)
        if session.owner_user_id != user.id:
            raise PermissionError("Solo quien conduce la sesión aplica sus cuestionarios")
        questionnaire_id = self.expected(session, ResponseMoment(moment))
        if questionnaire_id is None:
            raise ResponseConflict("Esta sesión no tiene ese cuestionario")
        questionnaire = self.repository.get(questionnaire_id)
        if questionnaire is None:
            raise QuestionnaireNotFound(questionnaire_id)
        return questionnaire

    def submit(self, user: User, session_id: str, moment: ResponseMoment | str, answers: dict,
               entry_mode: EntryMode | str) -> QuestionnaireResponse:
        """Registra las respuestas tal como se dieron. Exige las obligatorias."""
        store = self._response_store()
        moment = ResponseMoment(moment)
        questionnaire = self.pending_for(user, session_id, moment)
        session = self._session(session_id)
        if store.get(session.id, moment.value) is not None:
            raise ResponseConflict("Este cuestionario ya se respondió en la sesión")
        response = store.add(QuestionnaireResponse(
            id=str(uuid4()), session_id=session.id, questionnaire_id=questionnaire.id, moment=moment,
            answers=questionnaire.normalize_answers(answers), entry_mode=entry_mode,
            recorded_by_user_id=user.id, submitted_at=self.clock()))
        self.audit.record(user, AuditAction.CREATE, RESPONSE, response.id)
        return response

    def answered(self, session_id: str, moment: ResponseMoment | str) -> bool:
        return (self.responses is not None
                and self.responses.get(session_id, ResponseMoment(moment).value) is not None)

    def pre_completed(self, session: EmotionalSession) -> bool:
        """Si el analizador puede empezar: sin cuestionario previo, o ya respondido."""
        if session.pre_questionnaire_id is None:
            return True
        return self.responses is not None and self.responses.get(session.id, ResponseMoment.PRE.value) is not None

    def responses_for(self, user: User, session_id: str) -> Sequence[tuple[QuestionnaireResponse, Questionnaire]]:
        """Respuestas de la sesión con su versión exacta del cuestionario. Solo
        quien condujo la sesión y su docente; cada consulta queda en la auditoría."""
        session = self._session(session_id)
        if self.session_access is None or not self.session_access(user, session):
            self.audit.record(user, AuditAction.VIEW, RESPONSE, session.id, AuditResult.DENIED)
            raise PermissionError("No tienes acceso a las respuestas de esta sesión")
        items = self._response_store().list_for_session(session.id)
        self.audit.record(user, AuditAction.VIEW, RESPONSE, session.id)
        result = []
        for item in items:
            questionnaire = self.repository.get(item.questionnaire_id)
            if questionnaire is not None:
                result.append((item, questionnaire))
        return result
