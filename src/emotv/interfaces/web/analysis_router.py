from __future__ import annotations

import asyncio
from collections.abc import Callable
import json

import cv2
import jwt
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from emotv.application import (
    ActivityCatalog,
    AuthenticationService,
    AuthorizationService,
    BrowserActivityService,
    SessionService,
)
from emotv.application.ports import StudentRepository, UserRepository
from emotv.domain import AccessAction, Activity, Role, SessionState


ProcessorFactory = Callable[[Activity], BrowserActivityService]
MAX_FRAME_BYTES = 2_500_000


def create_analysis_router(
    sessions: SessionService | None,
    activities: ActivityCatalog | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    students: StudentRepository | None,
    processor_factory: ProcessorFactory | None,
    authorization: AuthorizationService | None = None,
) -> APIRouter:
    router = APIRouter(tags=["analysis"])
    policy = authorization or AuthorizationService()

    @router.websocket("/ws/activity")
    async def activity_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        processor: BrowserActivityService | None = None
        active_session_id: str | None = None
        try:
            if any(value is None for value in (
                sessions, activities, authentication, users, students, processor_factory
            )):
                await _error(websocket, "Análisis no configurado", 1011)
                return
            assert sessions and activities and authentication and users and students
            assert processor_factory

            credentials = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            if credentials.get("type") != "authenticate":
                await _error(websocket, "Autenticación requerida", 4401)
                return
            try:
                claims = authentication.decode_access_token(str(credentials.get("token", "")))
            except jwt.InvalidTokenError:
                await _error(websocket, "Token inválido o vencido", 4401)
                return
            user = users.get_by_id(str(claims.get("sub", "")))
            if user is None or not user.is_active:
                await _error(websocket, "Usuario no autorizado", 4401)
                return

            session = sessions.get_session(str(credentials.get("session_id", "")))
            if session is None:
                await _error(websocket, "Sesión no encontrada", 4404)
                return
            actor = students.get_by_user_id(user.id) if user.role is Role.STUDENT else None
            try:
                policy.require(
                    user,
                    AccessAction.VIEW_SESSION,
                    resource_student_id=session.student_id,
                    actor_student_id=actor.id if actor else None,
                )
            except PermissionError:
                await _error(websocket, "No tienes acceso a esta sesión", 4403)
                return
            if session.state is not SessionState.IN_PROGRESS:
                await _error(websocket, "La sesión no está en progreso", 4409)
                return
            active_session_id = session.id

            activity_id = str(credentials.get("activity_id", "")).strip().lower()
            if not activity_id or session.activity_id != activity_id:
                await _error(websocket, "La actividad no coincide con la sesión", 4409)
                return
            try:
                activity = activities.get(activity_id)
            except KeyError:
                await _error(websocket, "Actividad no encontrada", 4404)
                return

            include_landmarks = bool(credentials.get("include_landmarks", False))
            processor = processor_factory(activity)
            await websocket.send_json({
                "type": "ready",
                "state": "analyzing_emotion",
                "message": "Cámara conectada. Ubica tu rostro en el centro",
                "progress": 0.0,
            })

            while True:
                event = await websocket.receive()
                if event["type"] == "websocket.disconnect":
                    break
                if event.get("text"):
                    command = json.loads(event["text"])
                    if command.get("type") == "cancel":
                        sessions.cancel_session(session.id)
                        await websocket.send_json({"type": "cancelled"})
                        break
                    continue
                frame_bytes = event.get("bytes")
                if not frame_bytes:
                    continue
                try:
                    authentication.decode_access_token(str(credentials.get("token", "")))
                except jwt.InvalidTokenError:
                    await _error(websocket, "Token vencido", 4401)
                    break
                current_user = users.get_by_id(user.id)
                if current_user is None or not current_user.is_active or current_user.role is not user.role:
                    await _error(websocket, "Usuario no autorizado", 4403)
                    break
                current_session = sessions.get_session(session.id)
                if current_session is None or current_session.state is not SessionState.IN_PROGRESS:
                    await _error(websocket, "La sesión ya no está en progreso", 4409)
                    break
                if session.student_id is not None:
                    try:
                        sessions.require_active_consent(session.student_id)
                    except PermissionError:
                        await _error(websocket, "Consentimiento revocado", 4403)
                        break
                if len(frame_bytes) > MAX_FRAME_BYTES:
                    await websocket.send_json({"type": "error", "message": "Frame demasiado grande"})
                    continue
                frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    await websocket.send_json({"type": "error", "message": "Frame inválido"})
                    continue

                status = await asyncio.to_thread(processor.process_frame, frame)
                payload: dict[str, object] = {
                    "type": "status",
                    "state": status.state.value,
                    "message": status.message,
                    "progress": status.exercise.progress if status.exercise else 0.0,
                    "elapsed_seconds": status.exercise.elapsed_seconds if status.exercise else 0.0,
                    "emotion": status.emotion.emotion if status.emotion else None,
                    "emotion_confidence": status.emotion.confidence if status.emotion else None,
                    "posture_detected": status.posture.detected if status.posture else False,
                    "landmarks": _landmarks(processor) if include_landmarks else None,
                }
                if status.completed:
                    sessions.complete_from_activity_status(session.id, status)
                    payload["type"] = "completed"
                await websocket.send_json(payload)
                if status.completed:
                    break
        except (WebSocketDisconnect, asyncio.TimeoutError):
            pass
        except Exception:
            try:
                await websocket.send_json({"type": "error", "message": "No se pudo procesar la actividad. Revisa la configuración del servidor."})
            except Exception:
                pass
        finally:
            if processor is not None:
                try:
                    await asyncio.to_thread(processor.close)
                except Exception:
                    pass
            if active_session_id is not None and sessions is not None:
                current = sessions.get_session(active_session_id)
                if current is not None and current.state is SessionState.IN_PROGRESS:
                    try:
                        sessions.cancel_session(active_session_id)
                    except RuntimeError:
                        pass
            try:
                await websocket.close()
            except Exception:
                pass

    return router


async def _error(websocket: WebSocket, message: str, code: int) -> None:
    await websocket.send_json({"type": "error", "message": message})
    await websocket.close(code=code)


def _landmarks(processor: BrowserActivityService) -> dict[str, dict[str, float]] | None:
    pose = processor.last_pose_result
    if pose is None or pose.landmarks is None:
        return None
    return {
        name: {
            "x": getattr(pose.landmarks, name).x,
            "y": getattr(pose.landmarks, name).y,
            "visibility": getattr(pose.landmarks, name).visibility,
        }
        for name in pose.landmarks.__dataclass_fields__
    }
