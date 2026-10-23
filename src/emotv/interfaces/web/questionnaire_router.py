"""Cuestionarios creados por quien conduce la sesión y sus respuestas.

Las respuestas se devuelven tal como se dieron: ninguna ruta suma, puntúa ni
interpreta. Las ven quien condujo la sesión y su docente; cada consulta se audita.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from emotv.application import AuthenticationService
from emotv.application.ports import UserRepository
from emotv.application.questionnaire_service import (
    QuestionnaireDraft,
    QuestionnaireNotFound,
    QuestionnaireService,
    ResponseConflict,
    ResponsesUnavailable,
)
from emotv.domain import User
from emotv.domain.questionnaire import MAX_QUESTIONS, Question, Questionnaire, QuestionnaireResponse
from emotv.interfaces.web.auth_router import create_current_user_dependency

AnswerValue = StrictInt | StrictStr | list[StrictStr]
QuestionKindValue = Literal["scale", "single_choice", "multiple_choice", "short_text", "faces"]


class QuestionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=36)
    kind: QuestionKindValue
    text: str = Field(min_length=1, max_length=300)
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=10)
    scale_points: int | None = None
    min_label: str | None = Field(default=None, max_length=60)
    max_label: str | None = Field(default=None, max_length=60)


class QuestionnaireRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=2000)
    questions: list[QuestionModel] = Field(min_length=1, max_length=MAX_QUESTIONS)


class ShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shared: bool


class QuestionnaireResponseModel(BaseModel):
    id: str
    family_id: str
    version: int
    title: str
    instructions: str
    questions: list[QuestionModel]
    created_at: datetime
    shared_with_group: bool
    owned_by_me: bool
    used: bool


class AnswersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, AnswerValue]
    entry_mode: Literal["participant", "conductor"]


class SessionResponseModel(BaseModel):
    """Respuestas tal como se dieron, con la versión exacta del cuestionario."""

    id: str
    moment: str
    entry_mode: str
    submitted_at: datetime
    questionnaire: QuestionnaireResponseModel
    answers: dict[str, AnswerValue]


class PendingQuestionnaire(BaseModel):
    questionnaire: QuestionnaireResponseModel
    answered: bool


def create_questionnaire_router(
    questionnaires: QuestionnaireService | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
) -> APIRouter:
    router = APIRouter(tags=["questionnaires"])
    current_user = create_current_user_dependency(authentication, users)

    def service() -> QuestionnaireService:
        if questionnaires is None:
            raise HTTPException(503, "Los cuestionarios no están configurados")
        return questionnaires

    def guarded(operation):
        try:
            return operation()
        except QuestionnaireNotFound as error:
            raise HTTPException(404, "Cuestionario o sesión no encontrados") from error
        except PermissionError as error:
            raise HTTPException(403, str(error)) from error
        except ResponsesUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except ResponseConflict as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    def to_model(item: Questionnaire, user: User, used: bool | None = None) -> QuestionnaireResponseModel:
        return QuestionnaireResponseModel(
            id=item.id, family_id=item.family_id, version=item.version, title=item.title,
            instructions=item.instructions, questions=[QuestionModel(**question.to_dict()) for question in item.questions],
            created_at=item.created_at, shared_with_group=item.shared_with_group,
            owned_by_me=item.owner_user_id == user.id,
            used=service().is_used(item) if used is None else used)

    def draft(request: QuestionnaireRequest) -> QuestionnaireDraft:
        def build():
            return tuple(Question(id=item.id, kind=item.kind, text=item.text, required=item.required,
                                  options=tuple(item.options), scale_points=item.scale_points,
                                  min_label=item.min_label, max_label=item.max_label) for item in request.questions)
        return QuestionnaireDraft(request.title, request.instructions, guarded(build))

    def response_model(item: QuestionnaireResponse, questionnaire: Questionnaire, user: User) -> SessionResponseModel:
        return SessionResponseModel(
            id=item.id, moment=item.moment.value, entry_mode=item.entry_mode.value, submitted_at=item.submitted_at,
            questionnaire=to_model(questionnaire, user, used=True), answers=item.answers)

    @router.get("/questionnaires", response_model=list[QuestionnaireResponseModel])
    def list_questionnaires(user: User = Depends(current_user)):
        return [to_model(item, user) for item in guarded(lambda: service().list_for(user))]

    @router.post("/questionnaires", response_model=QuestionnaireResponseModel, status_code=201)
    def create(request: QuestionnaireRequest, user: User = Depends(current_user)):
        return to_model(guarded(lambda: service().create(user, draft(request))), user)

    @router.post("/questionnaires/starter", response_model=QuestionnaireResponseModel, status_code=201)
    def create_starter(user: User = Depends(current_user)):
        """Copia a la cuenta la plantilla inicial con dos preguntas de caritas."""
        return to_model(guarded(lambda: service().create_starter(user)), user)

    @router.get("/questionnaires/{questionnaire_id}", response_model=QuestionnaireResponseModel)
    def get_questionnaire(questionnaire_id: str, user: User = Depends(current_user)):
        return to_model(guarded(lambda: service().get(user, questionnaire_id)), user)

    @router.put("/questionnaires/{questionnaire_id}", response_model=QuestionnaireResponseModel)
    def edit(questionnaire_id: str, request: QuestionnaireRequest, user: User = Depends(current_user)):
        """Si la versión ya se usó en una sesión, responde con una versión nueva."""
        return to_model(guarded(lambda: service().edit(user, questionnaire_id, draft(request))), user)

    @router.post("/questionnaires/{questionnaire_id}/copy", response_model=QuestionnaireResponseModel,
                 status_code=201)
    def copy(questionnaire_id: str, user: User = Depends(current_user)):
        return to_model(guarded(lambda: service().copy(user, questionnaire_id)), user)

    @router.put("/questionnaires/{questionnaire_id}/share", response_model=QuestionnaireResponseModel)
    def share(questionnaire_id: str, request: ShareRequest, user: User = Depends(current_user)):
        return to_model(guarded(lambda: service().share(user, questionnaire_id, request.shared)), user)

    @router.get("/sessions/{session_id}/questionnaires/{moment}", response_model=PendingQuestionnaire)
    def pending(session_id: str, moment: Literal["pre", "post"], user: User = Depends(current_user)):
        def run():
            questionnaire = service().pending_for(user, session_id, moment)
            return PendingQuestionnaire(questionnaire=to_model(questionnaire, user),
                                        answered=service().answered(session_id, moment))
        return guarded(run)

    @router.post("/sessions/{session_id}/questionnaires/{moment}", status_code=201)
    def submit(session_id: str, moment: Literal["pre", "post"], request: AnswersRequest,
               user: User = Depends(current_user)) -> dict[str, str]:
        response = guarded(lambda: service().submit(user, session_id, moment, request.answers, request.entry_mode))
        # Solo la confirmación: las respuestas no se repiten ni se resumen.
        return {"id": response.id, "moment": response.moment.value}

    @router.get("/sessions/{session_id}/questionnaire-responses", response_model=list[SessionResponseModel])
    def session_responses(session_id: str, user: User = Depends(current_user)):
        return [response_model(item, questionnaire, user)
                for item, questionnaire in guarded(lambda: service().responses_for(user, session_id))]

    return router
