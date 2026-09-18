from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from emotv.application.vision_service import VisionService
from emotv.application import ActivityCatalog, AuthenticationService, SessionService
from emotv.application import BrowserActivityService, PoseService
from emotv.config import DATABASE_URL, JWT_SECRET_KEY
from emotv.infrastructure.persistence import (
    PostgresUserRepository,
    PostgresStudentRepository,
    PostgresConsentRepository,
    PostgresSessionRepository,
    create_database_engine,
    create_session_factory,
)
from emotv.interfaces.web.auth_router import create_auth_router
from emotv.interfaces.web.auth_router import create_current_user_dependency
from emotv.interfaces.web.identity_router import create_identity_router
from emotv.infrastructure.persistence.postgres_activity_repository import PostgresActivityRepository
from emotv.domain import User, Role
from emotv.interfaces.web.security import configure_web_security, load_web_settings
from emotv.interfaces.web.activity_router import create_activity_router
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.session_router import create_session_router
from emotv.infrastructure.vision.emotion_classifier.emotion_frame_analyzer import (
    EmotionFrameAnalyzer,
)
from emotv.infrastructure.vision.emotion_classifier import create_emotion_classifier
from emotv.infrastructure.vision.emotion_classifier.model_admission import ServerModelAdmission

# Inicializar servicio de visión
vision_service = VisionService()

# Inicializar FastAPI
web_settings = load_web_settings()
app = FastAPI(title="EMOtv API", version="1.0.0", docs_url=None if web_settings.production else "/docs",
              redoc_url=None if web_settings.production else "/redoc",
              openapi_url=None if web_settings.production else "/openapi.json")
configure_web_security(app, web_settings)
activity_catalog = ActivityCatalog()
model_admission = ServerModelAdmission()

if DATABASE_URL and JWT_SECRET_KEY:
    database_engine = create_database_engine(DATABASE_URL)
    user_repository = PostgresUserRepository(create_session_factory(database_engine))
    database_sessions = create_session_factory(database_engine)
    student_repository = PostgresStudentRepository(database_sessions)
    consent_repository = PostgresConsentRepository(database_sessions)
    session_repository = PostgresSessionRepository(database_sessions)
    authentication_service = AuthenticationService(user_repository, JWT_SECRET_KEY)
    activity_catalog = ActivityCatalog(repository=PostgresActivityRepository(database_sessions))
    current_user = create_current_user_dependency(authentication_service, user_repository)
    app.include_router(create_identity_router(authentication_service, user_repository, student_repository, consent_repository))
    session_service = SessionService(
        session_repository,
        consent_repository=consent_repository,
        required_policy_version=(os.getenv("CONSENT_POLICY_VERSION", "").strip()
                                 if os.getenv("CONSENT_POLICY_VERSION", "").strip() and
                                 os.getenv("CONSENT_POLICY_URL", "").strip().startswith(("https://", "http://localhost", "http://127.0.0.1"))
                                 else "__policy_not_configured__"),
    )
    app.include_router(create_auth_router(authentication_service, user_repository))
    app.include_router(create_activity_router(
        activity_catalog,
        authentication_service,
        user_repository,
    ))
    app.include_router(create_session_router(
        session_service,
        authentication_service,
        user_repository,
        student_repository,
        activities=activity_catalog,
    ))
    app.include_router(create_analysis_router(
        session_service,
        activity_catalog,
        authentication_service,
        user_repository,
        student_repository,
        lambda activity: BrowserActivityService(
            activity,
            EmotionFrameAnalyzer(),
            PoseService(),
        ),
        model_processor_factory=lambda activity, model_id: BrowserActivityService(
            activity,
            EmotionFrameAnalyzer(classifier=create_emotion_classifier(model_id)),
            PoseService(),
        ),
        model_admission=model_admission.evaluate,
        emotion_analyzer_factory=lambda model_id: EmotionFrameAnalyzer(
            classifier=create_emotion_classifier(model_id),
        ),
        adaptive_processor_factory=lambda activity, analyzer, emotion: BrowserActivityService(
            activity, analyzer, PoseService(), initial_emotion=emotion,
        ),
    ))
else:
    authentication_service = None
    user_repository = None
    current_user = create_current_user_dependency(None, None)
    app.include_router(create_identity_router(None, None, None, None))
    app.include_router(create_auth_router(None, None))
    app.include_router(create_activity_router(None, None, None))
    app.include_router(create_session_router(None, None, None, None))
    app.include_router(create_analysis_router(None, None, None, None, None, None))


@app.on_event("startup")
async def startup_event():
    """Deja disponible la API sin bloquearla al abrir la cámara."""

    print("API EMOtv iniciada. La cámara permanece apagada.")


@app.on_event("shutdown")
async def shutdown_event():
    """Detiene el servicio al apagar la API."""
    vision_service.stop()
    print("VisionService detenido.")


@app.get("/")
async def root():
    return {"message": "EMOtv API. Visita /docs para documentación."}


@app.get("/video_feed")
async def video_feed(user: User = Depends(current_user)):
    """Endpoint para streaming MJPEG del video procesado."""
    if user.role is not Role.ADMIN:
        raise HTTPException(403, "La cámara del servidor es exclusiva de administración")
    async def generate():
        while vision_service.is_running:
            jpeg = vision_service.get_current_jpeg()
            if jpeg is not None:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' +
                    jpeg + b'\r\n'
                )
            # Limitar a ~12 FPS de salida para evitar acumulación de buffer
            await asyncio.sleep(1 / vision_service.stream_fps)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/emotion")
async def get_emotion(user: User = Depends(current_user)):
    if user.role is not Role.ADMIN:
        raise HTTPException(403, "Acceso exclusivo de administración")
    emotion, confidence = vision_service.get_current_emotion()
    return {"emotion": emotion, "confidence": confidence}


@app.get("/stats")
async def get_stats(user: User = Depends(current_user)):
    if user.role is not Role.ADMIN:
        raise HTTPException(403, "Acceso exclusivo de administración")
    return vision_service.get_current_stats()


def _control_camera(action: str) -> dict[str, str]:
    if action == "start":
        if not vision_service.is_running:
            vision_service.start()
            print("Cámara iniciada mediante control web.")
            return {"status": "started"}
        return {"status": "already_running"}
    if action == "stop":
        if vision_service.is_running:
            vision_service.stop()
            print("Cámara detenida mediante control web.")
            return {"status": "stopped"}
        return {"status": "already_stopped"}
    raise HTTPException(status_code=400, detail="action must be 'start' or 'stop'")


@app.post("/control/{action}")
async def control_camera_post(action: str, user: User = Depends(current_user)):
    """Control no cacheable usado por la interfaz web."""
    if user.role is not Role.ADMIN:
        raise HTTPException(403, "Solo administración puede controlar la cámara del servidor")
    return _control_camera(action)


@app.get("/control")
async def control_camera(action: str, user: User = Depends(current_user)):
    """Compatibilidad con el control existente por query string."""
    if user.role is not Role.ADMIN:
        raise HTTPException(403, "Solo administración puede controlar la cámara del servidor")
    return _control_camera(action)


@app.websocket("/ws/emotions")
async def websocket_emotions(websocket: WebSocket):
    await websocket.accept()
    try:
        import jwt
        if authentication_service is None or user_repository is None:
            await websocket.close(code=1011)
            return
        credentials = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        try:
            claims = authentication_service.decode_access_token(str(credentials.get("token", "")))
            user = user_repository.get_by_id(str(claims.get("sub", "")))
        except (jwt.InvalidTokenError, ValueError):
            await websocket.close(code=4401)
            return
        if (user is None or not user.is_active or user.must_change_password
                or claims.get("tv") != user.token_version
                or credentials.get("type") != "authenticate"):
            await websocket.close(code=4401)
            return
        if user.role is not Role.ADMIN:
            await websocket.close(code=4403)
            return
        while True:
            try:
                current_claims = authentication_service.decode_access_token(str(credentials.get("token", "")))
            except jwt.InvalidTokenError:
                await websocket.close(code=4401)
                return
            current = user_repository.get_by_id(user.id)
            if (current is None or not current.is_active or current.must_change_password
                    or current_claims.get("tv") != current.token_version
                    or current.role is not Role.ADMIN):
                await websocket.close(code=4403)
                return
            emotion, confidence = vision_service.get_current_emotion()
            stats = vision_service.get_current_stats()
            await websocket.send_text(json.dumps({
                "emotion": emotion,
                "confidence": confidence,
                "fps": stats["fps"],
                "faces": stats["faces_detected"],
            }))
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        print("WebSocket desconectado.")


# Servir archivos estáticos
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/web", response_class=HTMLResponse)
async def web_interface():
    index_path = static_dir / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(
                f.read(),
                headers={"Cache-Control": "no-store"},
            )
    return HTMLResponse("<h1>index.html no encontrado</h1>", status_code=404)
