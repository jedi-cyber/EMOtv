from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
from typing import Protocol

import cv2
import jwt
import numpy as np
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from emotv.interfaces.web.auth_router import create_current_user_dependency

from emotv.application import (
    ActivityCatalog,
    AuthenticationService,
    AuthorizationService,
    BrowserActivityService,
    SessionService,
)
from emotv.application.activity_recommendation_service import (
    ActivityRecommendationService,
    DEFAULT_ACTIVITIES_BY_EMOTION,
)
from emotv.application.emotion_stabilizer import EmotionStabilizer
from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.application.ports import StudentRepository, UserRepository
from emotv.domain import AccessAction, Activity, Role, SessionState, StabilizedEmotion


ProcessorFactory = Callable[[Activity], BrowserActivityService]
class EmotionAnalyzer(Protocol):
    def analyze(self, frame: np.ndarray) -> tuple[str, float] | None: ...


EmotionAnalyzerFactory = Callable[[str], EmotionAnalyzer]
AdaptiveProcessorFactory = Callable[[Activity, EmotionAnalyzer, StabilizedEmotion], BrowserActivityService]
MAX_FRAME_BYTES = 2_500_000


def create_analysis_router(
    sessions: SessionService | None,
    activities: ActivityCatalog | None,
    authentication: AuthenticationService | None,
    users: UserRepository | None,
    students: StudentRepository | None,
    processor_factory: ProcessorFactory | None,
    authorization: AuthorizationService | None = None,
    model_processor_factory: Callable[[Activity, str], BrowserActivityService] | None = None,
    model_admission: Callable[[str], dict] | None = None,
    emotion_analyzer_factory: EmotionAnalyzerFactory | None = None,
    adaptive_processor_factory: AdaptiveProcessorFactory | None = None,
) -> APIRouter:
    router = APIRouter(tags=["analysis"])
    policy = authorization or AuthorizationService()

    @router.get("/analysis/models")
    def available_models(user=Depends(create_current_user_dependency(authentication, users))):
        return [model_admission(model_id) if model_admission else
                dict(model_id=model_id, state="BLOCKED", reasons=["Evaluación de modelos no configurada"])
                for model_id in ("ferplus_onnx", "hardlyhumans_vit")]

    @router.websocket("/ws/activity")
    async def activity_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        processor: BrowserActivityService | None = None
        analyzer: EmotionAnalyzer | None = None
        stable_emotion: StabilizedEmotion | None = None
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
            if (user is None or not user.is_active or user.must_change_password
                    or claims.get("tv") != user.token_version):
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
            adaptive = not activity_id and session.activity_id is None
            activity: Activity | None = None
            if adaptive:
                if emotion_analyzer_factory is None or adaptive_processor_factory is None:
                    await _error(websocket, "Análisis emocional no configurado", 1011)
                    return
            else:
                if not activity_id or session.activity_id != activity_id:
                    await _error(websocket, "La actividad no coincide con la sesión", 4409)
                    return
                try:
                    activity = activities.get(activity_id)
                except KeyError:
                    await _error(websocket, "Actividad no encontrada", 4404)
                    return

            include_landmarks = bool(credentials.get("include_landmarks", False))
            model_id = credentials.get("emotion_model_id", "ferplus_onnx")
            if model_id not in ("ferplus_onnx", "hardlyhumans_vit"):
                await _error(websocket, "Modelo facial no permitido", 4400)
                return
            if model_id != "ferplus_onnx" and model_processor_factory is None:
                await _error(websocket, "El modelo seleccionado no está configurado en el servidor", 1011)
                return
            admission = None
            if model_admission is not None:
                admission = await asyncio.to_thread(model_admission, model_id)
                if admission.get("state") not in ("SUPPORTED", "WARNING"):
                    await websocket.send_json({"type": "error", "message": "Modelo bloqueado: " + "; ".join(admission.get("reasons", [])), "admission": admission})
                    await websocket.close(code=4409)
                    return
            try:
                if adaptive:
                    assert emotion_analyzer_factory is not None
                    analyzer = await asyncio.to_thread(emotion_analyzer_factory, model_id)
                elif model_processor_factory is not None:
                    assert activity is not None
                    processor = await asyncio.to_thread(model_processor_factory, activity, model_id)
                else:
                    assert activity is not None
                    processor = await asyncio.to_thread(processor_factory, activity)
            except (FileNotFoundError, RuntimeError):
                await _error(websocket, "Modelo no disponible. Revisa sus pesos y dependencias en el servidor o selecciona FER+", 1011)
                return
            model_version = EmotionModelCatalog().get(model_id).version
            sessions.record_emotion_model(session.id, model_id, model_version)
            stabilizer = EmotionStabilizer()
            await websocket.send_json({
                "type": "ready",
                "state": "analyzing_emotion",
                "message": "Cámara conectada. Ubica tu rostro en el centro",
                "progress": 0.0,
                "emotion_model_id": model_id,
                "emotion_model_version": model_version,
                "admission": admission,
            })

            while True:
                event = await websocket.receive()
                if event["type"] == "websocket.disconnect":
                    break
                if event.get("text"):
                    try:
                        command = json.loads(event["text"])
                    except (ValueError, TypeError):
                        await websocket.send_json({"type": "error", "message": "Comando inválido"})
                        continue
                    if command.get("type") == "cancel":
                        sessions.cancel_session(session.id)
                        await websocket.send_json({"type": "cancelled"})
                        break
                    if command.get("type") == "select_activity" and adaptive:
                        if stable_emotion is None or processor is not None:
                            await websocket.send_json({"type": "error", "message": "Primero completa el reconocimiento facial"})
                            continue
                        try:
                            current_claims = authentication.decode_access_token(str(credentials.get("token", "")))
                            current_user = users.get_by_id(user.id)
                            current_session = sessions.get_session(session.id)
                            if (current_user is None or not current_user.is_active or current_user.must_change_password
                                    or current_claims.get("tv") != current_user.token_version
                                    or current_user.role is not user.role
                                    or current_session is None or current_session.state is not SessionState.IN_PROGRESS):
                                raise PermissionError("Sesión no autorizada")
                            sessions.require_active_consent(session.student_id)
                            selected = activities.get(str(command.get("activity_id", "")).strip())
                            sessions.assign_activity(session.id, selected.id)
                            assert analyzer is not None and adaptive_processor_factory is not None
                            processor = await asyncio.to_thread(
                                adaptive_processor_factory, selected, analyzer, stable_emotion,
                            )
                        except (jwt.InvalidTokenError, PermissionError, KeyError, ValueError):
                            await _error(websocket, "No se pudo iniciar la actividad seleccionada", 4403)
                            break
                        await websocket.send_json({
                            "type": "activity_started", "state": "waiting_for_posture",
                            "message": "Adopta la postura indicada", "progress": 0.0,
                            "activity": _activity_payload(selected),
                            "emotion": stable_emotion.emotion,
                            "emotion_confidence": stable_emotion.confidence,
                        })
                    continue
                frame_bytes = event.get("bytes")
                if not frame_bytes:
                    continue
                try:
                    current_claims = authentication.decode_access_token(str(credentials.get("token", "")))
                except jwt.InvalidTokenError:
                    await _error(websocket, "Token vencido", 4401)
                    break
                current_user = users.get_by_id(user.id)
                if (current_user is None or not current_user.is_active or current_user.must_change_password
                        or current_claims.get("tv") != current_user.token_version
                        or current_user.role is not user.role):
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

                if adaptive and processor is None:
                    if stable_emotion is not None:
                        continue
                    assert analyzer is not None
                    prediction = await asyncio.to_thread(analyzer.analyze, frame)
                    if prediction is not None:
                        stable_emotion = stabilizer.update(*prediction)
                    if stable_emotion is None:
                        await websocket.send_json({
                            "type": "status", "state": "analyzing_emotion",
                            "message": "Ubica el rostro frente a la cámara" if prediction is None else "Analizando la expresión facial",
                            "progress": 0.0,
                        })
                        continue
                    available_ids = set(activities.ids)
                    mapping = {
                        emotion: tuple(item_id for item_id in ids if item_id in available_ids)
                        for emotion, ids in DEFAULT_ACTIVITIES_BY_EMOTION.items()
                    }
                    recommendation = ActivityRecommendationService(activities, mapping).recommend(
                        stable_emotion.emotion,
                    )
                    await websocket.send_json({
                        "type": "recommendation", "state": "choosing_activity",
                        "message": "Expresión reconocida. Revisa la actividad sugerida",
                        "emotion": stable_emotion.emotion,
                        "emotion_confidence": stable_emotion.confidence,
                        "activity": _activity_payload(recommendation) if recommendation else None,
                        "activities": [_activity_payload(item) for item in activities.list_all()],
                        "progress": 0.0,
                    })
                    continue

                assert processor is not None
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


def _activity_payload(activity: Activity) -> dict[str, object]:
    return {
        "id": activity.id,
        "name": activity.name,
        "description": activity.description,
        "required_posture": activity.required_posture.value,
        "duration_seconds": activity.duration_seconds,
        "repetitions": activity.repetitions,
    }


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
