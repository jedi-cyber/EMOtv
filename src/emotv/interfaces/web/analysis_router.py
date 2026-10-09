from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import time
from typing import Protocol

import cv2
import jwt
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError
from emotv.interfaces.web.auth_router import create_current_user_dependency

from emotv.application import (
    ActivityCatalog,
    AuthenticationService,
    AuthorizationService,
    BrowserActivityService,
    SessionService,
)
from emotv.application.activity_recommendation_service import ActivityRecommendationService
from emotv.application.ports.recommendation_repository import RecommendationSource
from emotv.application.emotion_stabilizer import EmotionStabilizer
from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.application.live_expression import LiveExpressionTracker, LiveReading
from emotv.application.ports import StudentRepository, UserRepository
from emotv.config import LiveExpressionSettings
from emotv.domain import AccessAction, Activity, Role, SessionState, StabilizedEmotion


ProcessorFactory = Callable[[Activity], BrowserActivityService]
class EmotionAnalyzer(Protocol):
    def analyze(self, frame: np.ndarray) -> tuple[str, float] | None: ...


EmotionAnalyzerFactory = Callable[[str], EmotionAnalyzer]
AdaptiveProcessorFactory = Callable[[Activity, EmotionAnalyzer, StabilizedEmotion], BrowserActivityService]
MAX_FRAME_BYTES = 2_500_000
DEFAULT_EMOTION_MODEL_ID = "ferplus_onnx"
EMOTION_MODEL_IDS = (DEFAULT_EMOTION_MODEL_ID, "hardlyhumans_vit")
# Estados en los que la sesión sigue abierta en el WebSocket.
OPEN_STATES = (SessionState.IN_PROGRESS, SessionState.RECOGNIZED)

logger = logging.getLogger(__name__)

# Mensaje para el estudiante según la etapa que falló; el detalle técnico va
# solo al log del servidor (nunca datos de imagen).
STAGE_MESSAGES = {
    "recognition": "Falló el reconocimiento de la expresión. Intenta de nuevo en unos minutos.",
    "activity": "Falló la verificación de la actividad. Si ya registraste tu expresión, se conserva.",
    "persistence": "No se pudo guardar el estado de la sesión. Intenta de nuevo en unos minutos.",
    "server": "Ocurrió un error inesperado en el análisis. Intenta de nuevo en unos minutos.",
}
RECOMMENDATION_UNAVAILABLE = (
    "No se pudo calcular la actividad recomendada. Tu expresión quedó registrada; "
    "puedes elegir una actividad de la lista o finalizar sin actividad."
)


class AnalysisStageError(Exception):
    """Fallo de una etapa concreta del análisis (reconocimiento o actividad)."""

    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


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
    live_settings: LiveExpressionSettings | None = None,
    live_clock: Callable[[], float] | None = None,
    expression_info: Callable[[str], dict[str, object] | None] | None = None,
    recommendations: RecommendationSource | None = None,
) -> APIRouter:
    router = APIRouter(tags=["analysis"])
    live = live_settings or LiveExpressionSettings()
    policy = authorization or AuthorizationService()
    # Un recomendador por router y sin estado mutable: lee las asociaciones en
    # cada recomendación, así que sirve igual con varias conexiones y procesos.
    recommender = (
        ActivityRecommendationService(activities, source=recommendations) if activities is not None else None
    )

    @router.get("/analysis/models")
    def available_models(user=Depends(create_current_user_dependency(authentication, users))):
        # Elegir modelo es una tarea de administración; el estudiante usa siempre FER+.
        if user.role is not Role.ADMIN:
            raise HTTPException(403, "Solo administración puede consultar y elegir modelos faciales")
        return [model_admission(model_id) if model_admission else
                dict(model_id=model_id, state="BLOCKED", reasons=["Evaluación de modelos no configurada"])
                for model_id in EMOTION_MODEL_IDS]

    @router.websocket("/ws/activity")
    async def activity_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        processor: BrowserActivityService | None = None
        analyzer: EmotionAnalyzer | None = None
        recognized: StabilizedEmotion | None = None
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
            if user.role is Role.PSYCHOLOGIST:
                # Consultar sesiones asignadas no autoriza a enviar frames de
                # otra cámara a la sesión de un estudiante.
                await _error(websocket, "El análisis lo realiza el estudiante desde su cuenta", 4403)
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
            model_id = credentials.get("emotion_model_id", DEFAULT_EMOTION_MODEL_ID)
            if model_id not in EMOTION_MODEL_IDS:
                await _error(websocket, "Modelo facial no permitido", 4400)
                return
            if user.role is not Role.ADMIN and model_id != DEFAULT_EMOTION_MODEL_ID:
                await _error(websocket, "Solo administración puede elegir otro modelo facial", 4403)
                return
            if model_id != DEFAULT_EMOTION_MODEL_ID and model_processor_factory is None:
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
            tracker = LiveExpressionTracker(
                EmotionStabilizer(),
                stable_seconds=live.stable_seconds,
                min_confidence=live.min_confidence,
                clock=live_clock or time.monotonic,
            )
            await websocket.send_json({
                "type": "ready",
                "state": "live" if adaptive else "analyzing_emotion",
                "message": "Cámara conectada. Ubica tu rostro en el centro",
                "progress": 0.0,
                "emotion_model_id": model_id,
                "emotion_model_version": model_version,
                "admission": admission,
                "live_stable_seconds": live.stable_seconds,
                "live_min_confidence": live.min_confidence,
            })

            def require_authorized(*states: SessionState) -> None:
                """Revalida token, cuenta, estado de la sesión y consentimiento."""
                current_claims = authentication.decode_access_token(str(credentials.get("token", "")))
                current_user = users.get_by_id(user.id)
                current_session = sessions.get_session(session.id)
                if (current_user is None or not current_user.is_active or current_user.must_change_password
                        or current_claims.get("tv") != current_user.token_version
                        or current_user.role is not user.role
                        or current_session is None or current_session.state not in states):
                    raise PermissionError("Sesión no autorizada")
                sessions.require_active_consent(session.student_id)

            def recommendation_message(expression: StabilizedEmotion) -> dict[str, object]:
                assert recommender is not None
                notice: str | None = None
                try:
                    # La variación sale del historial del estudiante (su última
                    # actividad), no de memoria del proceso.
                    recent_ids: tuple[str, ...] = ()
                    if session.student_id:
                        previous = sorted(
                            (item for item in sessions.list_sessions_by_student(session.student_id)
                             if item.id != session.id and item.activity_id),
                            key=lambda item: item.started_at, reverse=True,
                        )
                        recent_ids = tuple(item.activity_id for item in previous[:1] if item.activity_id)
                    recommendation = recommender.recommend_varied(expression.emotion, exclude_ids=recent_ids)
                except SQLAlchemyError:
                    # La recomendación es opcional: con la expresión ya guardada,
                    # el estudiante puede elegir de la lista o terminar.
                    logger.exception("Etapa de recomendación fallida en la sesión %s", session.id)
                    recommendation, notice = None, RECOMMENDATION_UNAVAILABLE
                return {
                    "type": "recommendation", "state": "choosing_activity",
                    "message": "Expresión registrada. Revisa la actividad sugerida",
                    "emotion": expression.emotion,
                    "emotion_confidence": expression.confidence,
                    "activity": _activity_payload(recommendation) if recommendation else None,
                    "activities": [_activity_payload(item) for item in activities.list_all()],
                    # Texto educativo fijo del catálogo; nunca generado por un LLM.
                    "expression": expression_info(expression.emotion) if expression_info else None,
                    "notice": notice,
                    "progress": 0.0,
                }

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
                    command_type = command.get("type") if isinstance(command, dict) else None
                    if command_type == "cancel":
                        closed = sessions.cancel_session(session.id)
                        await websocket.send_json({
                            "type": "cancelled",
                            "recognition_kept": closed.recognized_at is not None,
                            "exercise_result": closed.exercise_result,
                        })
                        break
                    if command_type == "confirm_expression" and adaptive:
                        if recognized is not None:
                            await websocket.send_json({"type": "confirm_rejected", "message": "Esta sesión ya registró una expresión. Inicia una nueva para registrar otra."})
                            continue
                        try:
                            require_authorized(SessionState.IN_PROGRESS)
                        except (jwt.InvalidTokenError, PermissionError):
                            await _error(websocket, "No se pudo registrar la expresión", 4403)
                            break
                        # El servidor registra su propio último resultado estable;
                        # cualquier etiqueta que envíe el cliente se ignora.
                        try:
                            candidate = tracker.confirm()
                        except ValueError as reason:
                            await websocket.send_json({"type": "confirm_rejected", "message": str(reason)})
                            continue
                        stored = sessions.record_recognition(
                            session.id, candidate.emotion, candidate.confidence, model_id, model_version,
                        )
                        recognized = candidate
                        await websocket.send_json({
                            "type": "recognized", "state": "recognized",
                            "message": "Expresión registrada",
                            "emotion": stored.initial_emotion,
                            "emotion_confidence": stored.emotion_confidence,
                            "recognized_at": stored.recognized_at.isoformat() if stored.recognized_at else None,
                        })
                        await websocket.send_json(recommendation_message(recognized))
                        continue
                    if command_type == "finish_without_activity" and adaptive:
                        if recognized is None or processor is not None:
                            await websocket.send_json({"type": "error", "message": "Primero registra una expresión"})
                            continue
                        finished = sessions.finish_without_activity(session.id)
                        await websocket.send_json({
                            "type": "completed", "state": "completed",
                            "message": "Sesión finalizada sin actividad. Tu expresión quedó registrada.",
                            "emotion": finished.initial_emotion,
                            "emotion_confidence": finished.emotion_confidence,
                            "exercise_result": finished.exercise_result,
                            "progress": 0.0,
                        })
                        break
                    if command_type == "select_activity" and adaptive:
                        if recognized is None or processor is not None:
                            await websocket.send_json({"type": "error", "message": "Primero registra una expresión"})
                            continue
                        try:
                            require_authorized(SessionState.RECOGNIZED)
                            selected = activities.get(str(command.get("activity_id", "")).strip())
                            sessions.assign_activity(session.id, selected.id)
                        except (jwt.InvalidTokenError, PermissionError, KeyError, ValueError):
                            await _error(websocket, "No se pudo iniciar la actividad seleccionada", 4403)
                            break
                        assert analyzer is not None and adaptive_processor_factory is not None
                        try:
                            processor = await asyncio.to_thread(
                                adaptive_processor_factory, selected, analyzer, recognized,
                            )
                        except (OSError, RuntimeError, ValueError) as error:
                            # Pesos de pose ausentes o MediaPipe que no arranca.
                            raise AnalysisStageError("activity") from error
                        await websocket.send_json({
                            "type": "activity_started", "state": "waiting_for_posture",
                            "message": "Adopta la postura indicada", "progress": 0.0,
                            "activity": _activity_payload(selected),
                            "emotion": recognized.emotion,
                            "emotion_confidence": recognized.confidence,
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
                    await _error(websocket, "Usuario no autorizado", 4401)
                    break
                current_session = sessions.get_session(session.id)
                if current_session is None or current_session.state not in OPEN_STATES:
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
                    if recognized is not None:
                        # Expresión registrada y actividad sin elegir: no hay nada que analizar.
                        continue
                    assert analyzer is not None
                    # Fase en vivo: un mensaje por frame procesado y nada persistido.
                    try:
                        prediction, distribution = await asyncio.to_thread(_analyze_detailed, analyzer, frame)
                    except (cv2.error, OSError, RuntimeError, ValueError) as error:
                        raise AnalysisStageError("recognition") from error
                    reading = tracker.update(prediction, distribution)
                    await websocket.send_json(_live_message(reading, live))
                    continue

                assert processor is not None
                try:
                    status = await asyncio.to_thread(processor.process_frame, frame)
                except (cv2.error, OSError, RuntimeError, ValueError) as error:
                    raise AnalysisStageError("activity") from error
                payload: dict[str, object] = {
                    "type": "status",
                    "state": status.state.value,
                    "message": status.message,
                    "progress": status.exercise.progress if status.exercise else 0.0,
                    "elapsed_seconds": status.exercise.elapsed_seconds if status.exercise else 0.0,
                    "emotion": status.emotion.emotion if status.emotion else None,
                    "emotion_confidence": status.emotion.confidence if status.emotion else None,
                    "posture_detected": status.posture.detected if status.posture else False,
                    "step_index": status.step_index,
                    "step_count": status.step_count,
                    "step": _step_payload(getattr(processor, "current_step", processor.activity.steps[0])),
                    "landmarks": _landmarks(processor) if include_landmarks else None,
                }
                if status.completed:
                    stored = sessions.complete_from_activity_status(session.id, status)
                    payload["type"] = "completed"
                    payload["exercise_result"] = stored.exercise_result
                    # La expresión registrada en vivo prevalece sobre la del procesador.
                    payload["emotion"] = stored.initial_emotion
                    payload["emotion_confidence"] = stored.emotion_confidence
                await websocket.send_json(payload)
                if status.completed:
                    break
        except (WebSocketDisconnect, asyncio.TimeoutError):
            pass
        except AnalysisStageError as error:
            logger.error("Etapa %s fallida en la sesión %s", error.stage, active_session_id, exc_info=error.__cause__)
            await _report_stage(websocket, error.stage)
        except SQLAlchemyError:
            logger.exception("Error de base de datos durante el análisis de la sesión %s", active_session_id)
            await _report_stage(websocket, "persistence")
        except Exception:
            # Último recurso: el detalle queda en el log y el estudiante recibe un mensaje claro.
            logger.exception("Error inesperado durante el análisis de la sesión %s", active_session_id)
            await _report_stage(websocket, "server")
        finally:
            # Primero lo síncrono: si la tarea se canceló (apagado del servidor),
            # cualquier await de este bloque puede interrumpirse y la sesión
            # quedaría abierta.
            if active_session_id is not None and sessions is not None:
                current = sessions.get_session(active_session_id)
                if current is not None and current.state in OPEN_STATES:
                    # Con expresión registrada, cancel_session conserva la sesión
                    # (completada con actividad cancelada); sin ella, la cancela.
                    try:
                        sessions.cancel_session(active_session_id)
                    except RuntimeError:
                        pass
            if processor is not None:
                try:
                    processor.close()  # Libera MediaPipe; es rápido y no debe depender de un await.
                except Exception:
                    logger.exception("No se pudo cerrar el procesador de la sesión %s", active_session_id)
            try:
                await websocket.close()
            except Exception:
                pass

    return router


async def _report_stage(websocket: WebSocket, stage: str) -> None:
    try:
        await websocket.send_json({"type": "error", "stage": stage, "message": STAGE_MESSAGES[stage]})
    except (WebSocketDisconnect, RuntimeError):
        pass  # El cliente ya se desconectó; el fallo quedó en el log.


async def _error(websocket: WebSocket, message: str, code: int) -> None:
    # "code" permite al navegador distinguir una sesión vencida (4401) sin
    # depender del evento de cierre, que puede llegar después del mensaje.
    await websocket.send_json({"type": "error", "message": message, "code": code})
    await websocket.close(code=code)


def _analyze_detailed(
    analyzer: EmotionAnalyzer, frame: np.ndarray,
) -> tuple[tuple[str, float] | None, dict[str, float] | None]:
    detailed = getattr(analyzer, "analyze_detailed", None)
    if detailed is None:
        return analyzer.analyze(frame), None
    result = detailed(frame)
    return (None, None) if result is None else result


def _live_message(reading: LiveReading, live: LiveExpressionSettings) -> dict[str, object]:
    expression = reading.expression
    return {
        "type": "live",
        "state": "live",
        "face_detected": reading.face_detected,
        "emotion": expression.emotion if expression else None,
        "emotion_confidence": expression.confidence if expression else None,
        "top": [{"emotion": label, "probability": probability} for label, probability in reading.top],
        "stable_seconds": round(reading.stable_seconds, 2),
        "required_stable_seconds": live.stable_seconds,
        "can_confirm": reading.can_confirm,
        "blocked_reason": reading.blocked_reason,
    }


def _activity_payload(activity: Activity) -> dict[str, object]:
    return {
        "id": activity.id,
        "name": activity.name,
        "description": activity.description,
        "required_posture": activity.required_posture.value,
        "duration_seconds": activity.duration_seconds,
        "repetitions": activity.repetitions,
        "steps": [_step_payload(step) for step in activity.steps],
    }


def _step_payload(step) -> dict[str, object]:
    return {"posture": step.posture.value, "instruction": step.instruction,
            "duration_seconds": step.duration_seconds}


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
