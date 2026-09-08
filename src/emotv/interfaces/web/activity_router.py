from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from emotv.application import ActivityCatalog, AuthenticationService, AuthorizationService
from emotv.application.ports import UserRepository
from emotv.domain import AccessAction, Activity, PostureId, User
from emotv.interfaces.web.auth_router import create_current_user_dependency


class ActivityRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    required_posture: PostureId
    duration_seconds: float = Field(gt=0)
    repetitions: int = Field(default=1, ge=1)

    def to_domain(self) -> Activity:
        return Activity(**self.model_dump())


class ActivityResponse(BaseModel):
    id: str
    name: str
    description: str
    required_posture: PostureId
    duration_seconds: float
    repetitions: int

    @classmethod
    def from_domain(cls, activity: Activity) -> "ActivityResponse":
        return cls(**{
            "id": activity.id,
            "name": activity.name,
            "description": activity.description,
            "required_posture": activity.required_posture,
            "duration_seconds": activity.duration_seconds,
            "repetitions": activity.repetitions,
        })


def create_activity_router(
    catalog: ActivityCatalog | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    authorization: AuthorizationService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/activities", tags=["activities"])
    policy = authorization or AuthorizationService()
    current_user = create_current_user_dependency(authentication, users)

    def configured_catalog() -> ActivityCatalog:
        if catalog is None:
            raise HTTPException(status_code=503, detail="Actividades no configuradas")
        return catalog

    def require_management(user: User) -> None:
        try:
            policy.require(user, AccessAction.MANAGE_ACTIVITIES)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error

    @router.get("", response_model=list[ActivityResponse])
    def list_activities(_: User = Depends(current_user)) -> list[ActivityResponse]:
        return [ActivityResponse.from_domain(item) for item in configured_catalog().list_all()]

    @router.get("/{activity_id}", response_model=ActivityResponse)
    def get_activity(
        activity_id: str,
        _: User = Depends(current_user),
    ) -> ActivityResponse:
        try:
            activity = configured_catalog().get(activity_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error.args[0])) from error
        return ActivityResponse.from_domain(activity)

    @router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
    def create_activity(
        request: ActivityRequest,
        user: User = Depends(current_user),
    ) -> ActivityResponse:
        require_management(user)
        try:
            activity = configured_catalog().add(request.to_domain())
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return ActivityResponse.from_domain(activity)

    @router.put("/{activity_id}", response_model=ActivityResponse)
    def update_activity(
        activity_id: str,
        request: ActivityRequest,
        user: User = Depends(current_user),
    ) -> ActivityResponse:
        require_management(user)
        try:
            activity = configured_catalog().update(activity_id, request.to_domain())
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error.args[0])) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return ActivityResponse.from_domain(activity)

    @router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_activity(
        activity_id: str,
        user: User = Depends(current_user),
    ) -> Response:
        require_management(user)
        try:
            configured_catalog().remove(activity_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error.args[0])) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
