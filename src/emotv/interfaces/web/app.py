"""API EMOtv. La cámara pertenece al navegador: el servidor solo recibe frames
por /ws/activity y nunca abre un dispositivo de captura propio."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from emotv.application import ActivityCatalog, AuthenticationService, AuthorizationService, SessionService
from emotv.application.consent_policy_service import ConsentPolicyService
from emotv.application import BrowserActivityService, PoseService
from emotv.config import (BASE_DIR, DATABASE_URL, JWT_SECRET_KEY, FLOWISE_API_URL,
                          FLOWISE_API_KEY, FLOWISE_TIMEOUT_SECONDS, get_consent_mode,
                          YUNET_PATH, EMOTION_MODEL_PATH, get_login_limits,
                          get_live_expression_settings)
from emotv.infrastructure.persistence import (
    PostgresUserRepository,
    PostgresStudentRepository,
    PostgresConsentRepository,
    PostgresSessionRepository,
    PostgresConsentPolicyRepository,
    PostgresLoginAttemptRepository,
    PostgresAssignmentRepository,
    PostgresExpressionInfoRepository,
    PostgresRecommendationRepository,
    create_database_engine,
    create_session_factory,
)
from emotv.application.login_throttle import LoginThrottle
from emotv.interfaces.web.auth_router import create_auth_router
from emotv.interfaces.web.identity_router import create_identity_router
from emotv.infrastructure.persistence.postgres_activity_repository import PostgresActivityRepository
from emotv.interfaces.web.security import configure_web_security, load_web_settings
from emotv.interfaces.web.activity_router import create_activity_router
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.session_router import create_session_router
from emotv.interfaces.web.chat_router import create_chat_router
from emotv.interfaces.web.expression_router import create_expression_router, expression_payload
from emotv.interfaces.web.recommendation_router import create_recommendation_router
from emotv.application.recommendation_config_service import RecommendationConfigService
from emotv.application.expression_catalog_service import ExpressionCatalogService
from emotv.infrastructure.chat import FlowiseClient
from emotv.infrastructure.vision.emotion_classifier.emotion_frame_analyzer import (
    EmotionFrameAnalyzer,
)
from emotv.infrastructure.vision.emotion_classifier import create_emotion_classifier
from emotv.infrastructure.vision.emotion_classifier.model_admission import ServerModelAdmission

# Inicializar FastAPI
web_settings = load_web_settings()
app = FastAPI(title="EMOtv API", version="1.0.0", docs_url=None if web_settings.production else "/docs",
              redoc_url=None if web_settings.production else "/redoc",
              openapi_url=None if web_settings.production else "/openapi.json")
configure_web_security(app, web_settings)
activity_catalog = ActivityCatalog()
model_admission = ServerModelAdmission()
consent_mode = get_consent_mode()

if DATABASE_URL and JWT_SECRET_KEY:
    database_engine = create_database_engine(DATABASE_URL)
    user_repository = PostgresUserRepository(create_session_factory(database_engine))
    database_sessions = create_session_factory(database_engine)
    student_repository = PostgresStudentRepository(database_sessions)
    consent_repository = PostgresConsentRepository(database_sessions)
    consent_policy_service = ConsentPolicyService(PostgresConsentPolicyRepository(database_sessions), consent_mode)
    session_repository = PostgresSessionRepository(database_sessions)
    authentication_service = AuthenticationService(user_repository, JWT_SECRET_KEY)
    activity_catalog = ActivityCatalog(repository=PostgresActivityRepository(database_sessions))
    assignment_repository = PostgresAssignmentRepository(database_sessions)
    expression_catalog = ExpressionCatalogService(PostgresExpressionInfoRepository(database_sessions))
    recommendation_repository = PostgresRecommendationRepository(database_sessions)
    recommendation_config = RecommendationConfigService(recommendation_repository, activity_catalog)
    app.include_router(create_recommendation_router(recommendation_config, authentication_service, user_repository))

    def expression_label(key: str) -> str:
        info = expression_catalog.get(key)
        return info.label_es if info else key

    app.include_router(create_expression_router(expression_catalog, authentication_service, user_repository))

    def expression_info_for(key: str) -> dict[str, object] | None:
        try:
            return expression_payload(expression_catalog.get(key))
        except SQLAlchemyError:
            return None  # La pantalla de resultado usa su texto de respaldo.

    # Psicología accede solo a estudiantes asignados; la misma política en todos los routers.
    authorization_service = AuthorizationService(assignment_repository.is_assigned)
    app.include_router(create_identity_router(authentication_service, user_repository, student_repository,
                                              consent_repository, consent_policy_service,
                                              assignments=assignment_repository))
    session_service = SessionService(
        session_repository,
        consent_repository=consent_repository,
        consent_policy_service=consent_policy_service,
    )
    login_throttle = LoginThrottle(PostgresLoginAttemptRepository(database_sessions), get_login_limits())
    app.include_router(create_auth_router(authentication_service, user_repository,
                                          login_throttle=login_throttle))
    app.include_router(create_activity_router(
        activity_catalog,
        authentication_service,
        user_repository,
        recommendations=recommendation_config,
        expression_label=expression_label,
    ))
    app.include_router(create_session_router(
        session_service,
        authentication_service,
        user_repository,
        student_repository,
        authorization=authorization_service,
        activities=activity_catalog,
        assignments=assignment_repository,
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
        authorization=authorization_service,
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
        live_settings=get_live_expression_settings(),
        expression_info=expression_info_for,
        recommendations=recommendation_repository,
    ))
    flowise_client = FlowiseClient(FLOWISE_API_URL, FLOWISE_API_KEY, FLOWISE_TIMEOUT_SECONDS) if FLOWISE_API_URL else None
    app.include_router(create_chat_router(flowise_client, authentication_service, user_repository))
else:
    app.include_router(create_identity_router(None, None, None, None))
    app.include_router(create_auth_router(None, None))
    app.include_router(create_activity_router(None, None, None))
    app.include_router(create_session_router(None, None, None, None))
    app.include_router(create_analysis_router(None, None, None, None, None, None))
    app.include_router(create_chat_router(None, None, None))
    app.include_router(create_expression_router(None, None, None))
    app.include_router(create_recommendation_router(None, None, None))


@app.on_event("startup")
async def startup_event():
    if DATABASE_URL and JWT_SECRET_KEY and consent_mode == "demo":
        consent_policy_service.ensure_demo_policy(BASE_DIR / "docs" / "consent-demo.md")


@app.get("/")
def root():
    """Estado simple; /health hace las comprobaciones de dependencias."""
    return {"service": "emotv-api", "status": "running"}


def _database_status() -> str:
    if not (DATABASE_URL and JWT_SECRET_KEY):
        return "not_configured"
    try:
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return "unavailable"
    return "ok"


@app.get("/health")
def health():
    """Estado mínimo para orquestadores; no expone rutas ni configuración."""
    checks = {
        "database": _database_status(),
        "face_detector": "ok" if YUNET_PATH.is_file() else "missing",
        "emotion_model": "ok" if EMOTION_MODEL_PATH.is_file() else "missing",
    }
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse({"status": "ok" if healthy else "unavailable", "checks": checks},
                        status_code=200 if healthy else 503)


