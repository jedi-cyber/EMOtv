from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from emotv.application.vision_service import VisionService
from emotv.application import ActivityCatalog, AuthenticationService, SessionService
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
from emotv.interfaces.web.activity_router import create_activity_router
from emotv.interfaces.web.session_router import create_session_router

# Inicializar servicio de visión
vision_service = VisionService()

# Inicializar FastAPI
app = FastAPI(title="EMOtv API", version="1.0.0")
activity_catalog = ActivityCatalog()

if DATABASE_URL and JWT_SECRET_KEY:
    database_engine = create_database_engine(DATABASE_URL)
    user_repository = PostgresUserRepository(create_session_factory(database_engine))
    database_sessions = create_session_factory(database_engine)
    student_repository = PostgresStudentRepository(database_sessions)
    consent_repository = PostgresConsentRepository(database_sessions)
    session_repository = PostgresSessionRepository(database_sessions)
    authentication_service = AuthenticationService(user_repository, JWT_SECRET_KEY)
    session_service = SessionService(
        session_repository,
        consent_repository=consent_repository,
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
    ))
else:
    app.include_router(create_auth_router(None, None))
    app.include_router(create_activity_router(None, None, None))
    app.include_router(create_session_router(None, None, None, None))


@app.on_event("startup")
async def startup_event():
    """Inicia el servicio de visión al arrancar la API."""
    vision_service.start()
    print("VisionService iniciado.")


@app.on_event("shutdown")
async def shutdown_event():
    """Detiene el servicio al apagar la API."""
    vision_service.stop()
    print("VisionService detenido.")


@app.get("/")
async def root():
    return {"message": "EMOtv API. Visita /docs para documentación."}


@app.get("/video_feed")
async def video_feed():
    """Endpoint para streaming MJPEG del video procesado."""
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
async def get_emotion():
    emotion, confidence = vision_service.get_current_emotion()
    return {"emotion": emotion, "confidence": confidence}


@app.get("/stats")
async def get_stats():
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
async def control_camera_post(action: str):
    """Control no cacheable usado por la interfaz web."""
    return _control_camera(action)


@app.get("/control")
async def control_camera(action: str):
    """Compatibilidad con el control existente por query string."""
    return _control_camera(action)


@app.websocket("/ws/emotions")
async def websocket_emotions(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            emotion, confidence = vision_service.get_current_emotion()
            stats = vision_service.get_current_stats()
            await websocket.send_text(json.dumps({
                "emotion": emotion,
                "confidence": confidence,
                "fps": stats["fps"],
                "faces": stats["faces_detected"],
            }))
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
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
