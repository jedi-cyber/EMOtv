"""API EMOtv. La cámara pertenece al navegador: el servidor solo recibe frames
por /ws/activity y nunca abre un dispositivo de captura propio."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from emotv import __version__
from emotv.domain import Role
from emotv.application import ActivityCatalog, AuthenticationService, AuthorizationService, SessionService
from emotv.application.consent_policy_service import ConsentPolicyService
from emotv.application import BrowserActivityService, PoseService
from emotv.config import (BASE_DIR, DATABASE_URL, JWT_SECRET_KEY, get_chat_settings,
                          get_consent_mode,
                          YUNET_PATH, EMOTION_MODEL_PATH, get_login_limits,
                          get_live_expression_settings, get_practice_settings, get_server_load_settings,
                          get_privacy_settings, get_sensitive_data_keys, get_mobile_min_app_version,
                          get_user_image_settings)
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
    PostgresChatRepository,
    PostgresLocalModelSettingsRepository,
    PostgresAuditRepository,
    PostgresCommitmentRepository,
    PostgresSessionErasureRepository,
    create_database_engine,
    create_session_factory,
)
from emotv.application.login_throttle import LoginThrottle
from emotv.interfaces.web.auth_router import create_auth_router
from emotv.interfaces.web.identity_router import create_identity_router
from emotv.infrastructure.persistence.postgres_activity_repository import PostgresActivityRepository
from emotv.interfaces.web.security import configure_web_security, load_web_settings
from emotv.interfaces.web.activity_router import create_activity_router
from emotv.interfaces.web.analysis_capacity import AnalysisCapacity
from emotv.interfaces.web.analysis_router import create_analysis_router
from emotv.interfaces.web.session_router import create_session_router, create_visible_sessions
from emotv.interfaces.web.mobile_router import create_mobile_router
from emotv.application.mobile_auth_service import MobileAuthService
from emotv.infrastructure.persistence import PostgresMobileSessionRepository
from emotv.interfaces.web.chat_router import create_chat_router
from emotv.interfaces.web.expression_router import create_expression_router, expression_payload
from emotv.interfaces.web.recommendation_router import create_recommendation_router
from emotv.interfaces.web.model_admin_router import create_model_admin_router
from emotv.application.local_model_service import LocalModelService
from emotv.application.audit_service import AuditService
from emotv.application.commitment_service import CommitmentService
from emotv.application.session_privacy_service import SessionPrivacyService
from emotv.interfaces.web.privacy_router import create_privacy_router
from emotv.interfaces.web.stimulus_router import create_stimulus_router
from emotv.interfaces.web.user_image_router import create_user_image_router
from emotv.application.protocol_service import ProtocolService
from emotv.application.stimulus_service import StimulusService
from emotv.application.user_image_service import UserImageService
from emotv.infrastructure.persistence.postgres_practice_repositories import (
    PostgresProtocolRepository,
    PostgresNoticeRepository,
    PostgresStimulusRepository,
)
from emotv.infrastructure.vision.person_detection import create_person_detector
from emotv.infrastructure.vision.stimulus_image import sanitize_stimulus_image
from emotv.application.questionnaire_service import QuestionnaireService
from emotv.infrastructure.persistence.postgres_questionnaire_repositories import (
    PostgresQuestionnaireRepository,
    PostgresQuestionnaireResponseRepository,
)
from emotv.interfaces.web.questionnaire_router import create_questionnaire_router
from emotv.application.emotion_model_catalog import EmotionModelCatalog
from emotv.application.guided_session_service import GuidedSessionService
from emotv.infrastructure.persistence.postgres_guided_repositories import PostgresGuidedSessionRepository
from emotv.infrastructure.vision.capture_quality import GuidedFrameAnalyzer, decode_frame
from emotv.interfaces.web.guided_router import create_guided_router
from emotv.interfaces.web.practice_validation_router import create_practice_validation_router
from emotv.application.practice_validation_service import PracticeValidationService
from emotv.application.session_insights_service import SessionInsightsService
from emotv.interfaces.web.insights_router import create_insights_router
from emotv.application.session_statistics_service import SessionStatisticsService
from emotv.interfaces.web.statistics_router import create_statistics_router
from emotv.application.exam_service import ExamService
from emotv.infrastructure.persistence.postgres_exam_repository import PostgresExamRepository
from emotv.interfaces.web.exam_router import create_exam_router
from emotv.application.report_service import ReportService
from emotv.infrastructure.persistence.postgres_report_repository import PostgresReportRepository
from emotv.interfaces.web.report_router import create_report_router
from emotv.shared.security.field_encryption import FieldEncryptionError, create_field_cipher
from emotv.application.recommendation_config_service import RecommendationConfigService
from emotv.application.expression_catalog_service import ExpressionCatalogService
from emotv.infrastructure.chat import N8nWebhookChatGateway
from emotv.application.chat_service import ChatService
from emotv.application.emi_knowledge import EmiKnowledge
from emotv.infrastructure.vision.emotion_classifier.emotion_frame_analyzer import (
    EmotionFrameAnalyzer,
)
from emotv.infrastructure.vision.emotion_classifier import ClassifierCache, create_emotion_classifier
from emotv.infrastructure.vision.emotion_classifier.model_admission import ServerModelAdmission

# Inicializar FastAPI
web_settings = load_web_settings()
app = FastAPI(title="EMOtv API", version=__version__, docs_url=None if web_settings.production else "/docs",
              redoc_url=None if web_settings.production else "/redoc",
              openapi_url=None if web_settings.production else "/openapi.json")
configure_web_security(app, web_settings)
activity_catalog = ActivityCatalog()
model_admission = ServerModelAdmission()
consent_mode = get_consent_mode()
chat_settings = get_chat_settings()
# Cupos de sesiones y análisis simultáneos, y pool de hilos propio del análisis.
server_load = get_server_load_settings()
analysis_capacity = AnalysisCapacity(server_load)
# Cada clasificador se carga una vez por proceso y lo comparten todas las sesiones;
# cada análisis usa ONNX_THREADS_PER_SESSION hilos y los cupos limitan cuántos corren a la vez.
classifiers = ClassifierCache(lambda model_id: create_emotion_classifier(
    model_id, intra_op_threads=server_load.onnx_threads_per_session))
chat_service: ChatService | None = None
privacy_settings = get_privacy_settings()
audit_service: AuditService | None = None
session_privacy_service: SessionPrivacyService | None = None
user_image_service: UserImageService | None = None
user_image_settings = get_user_image_settings()
RETENTION_INTERVAL_SECONDS = 24 * 60 * 60
retention_task: asyncio.Task | None = None
logger = logging.getLogger("emotv.api")


def _field_cipher():
    """Cifrado de campos sensibles; sin clave válida, las sesiones con protocolo no se activan."""
    try:
        cipher = create_field_cipher(get_sensitive_data_keys())
    except FieldEncryptionError as error:
        logger.error("Sesiones con protocolo desactivadas: %s", error)
        return None
    if cipher is None:
        log = logger.error if web_settings.production else logger.warning
        log("Sesiones con protocolo desactivadas: SENSITIVE_DATA_KEY no está configurada")
    return cipher

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
    # Conocimiento de EMOtv para Emi; se invalida cuando administración edita contenido.
    emi_knowledge = EmiKnowledge(activity_catalog.list_all, expression_catalog.list_all)
    recommendation_repository = PostgresRecommendationRepository(database_sessions)
    recommendation_config = RecommendationConfigService(recommendation_repository, activity_catalog)
    app.include_router(create_recommendation_router(recommendation_config, authentication_service, user_repository))

    def expression_label(key: str) -> str:
        info = expression_catalog.get(key)
        return info.label_es if info else key

    app.include_router(create_expression_router(expression_catalog, authentication_service, user_repository,
                                                on_change=emi_knowledge.invalidate))

    def expression_info_for(key: str) -> dict[str, object] | None:
        try:
            return expression_payload(expression_catalog.get(key))
        except SQLAlchemyError:
            return None  # La pantalla de resultado usa su texto de respaldo.

    audit_service = AuditService(PostgresAuditRepository(database_sessions))
    commitment_service = CommitmentService(PostgresCommitmentRepository(database_sessions), audit_service)

    def docente_of(user_id: str) -> str | None:
        """Docente vigente del usuario: el acceso sigue la asignación actual."""
        student = student_repository.get_by_user_id(user_id)
        assignment = assignment_repository.get_by_student(student.id) if student else None
        return assignment.psychologist_user_id if assignment else None

    def group_user_ids(docente_user_id: str) -> tuple[str, ...]:
        found = (student_repository.get_by_id(item.student_id)
                 for item in assignment_repository.list_by_psychologist(docente_user_id))
        return tuple(student.user_id for student in found if student is not None)

    field_cipher = _field_cipher()
    # Una sola regla de acceso a sesiones (can_access_session) en todos los routers.
    authorization_service = AuthorizationService(assignment_repository.is_assigned, docente_of)
    stimulus_service = StimulusService(PostgresStimulusRepository(database_sessions), audit_service, docente_of,
                                       sanitize_stimulus_image)
    def session_access(user, session) -> bool:
        actor = student_repository.get_by_user_id(user.id) if user.role is Role.STUDENT else None
        return authorization_service.can_access_session(user, session, actor_student_id=actor.id if actor else None)

    # Respuestas cifradas: sin SENSITIVE_DATA_KEY los cuestionarios se arman, pero no se aplican.
    questionnaire_service = QuestionnaireService(
        PostgresQuestionnaireRepository(database_sessions), audit_service, docente_of,
        responses=(PostgresQuestionnaireResponseRepository(database_sessions, field_cipher)
                   if field_cipher is not None else None),
        sessions=lambda session_id: session_repository.get_by_id(session_id),
        session_access=session_access)
    protocol_service = ProtocolService(PostgresProtocolRepository(database_sessions), stimulus_service,
                                       audit_service, docente_of, group_user_ids, questionnaires=questionnaire_service)
    app.include_router(create_questionnaire_router(questionnaire_service, authentication_service, user_repository))
    app.include_router(create_stimulus_router(stimulus_service, protocol_service, authentication_service,
                                              user_repository))
    # Imágenes propias: detección de personas en memoria y revisión del docente.
    user_image_service = UserImageService(
        stimulus_service.repository, PostgresNoticeRepository(database_sessions), audit_service, docente_of,
        group_user_ids, sanitize_stimulus_image,
        create_person_detector(user_image_settings.person_review_confidence), user_image_settings,
        protocols_using=protocol_service.repository.list_current_using)
    app.include_router(create_user_image_router(user_image_service, authentication_service, user_repository))
    app.include_router(create_privacy_router(commitment_service, audit_service, authentication_service,
                                             user_repository))
    app.include_router(create_identity_router(authentication_service, user_repository, student_repository,
                                              consent_repository, consent_policy_service,
                                              assignments=assignment_repository, audit=audit_service,
                                              privacy=privacy_settings))
    session_service = SessionService(
        session_repository,
        consent_repository=consent_repository,
        consent_policy_service=consent_policy_service,
    )
    # Retención y eliminación por sesión, con acta.
    session_privacy_service = SessionPrivacyService(
        session_service, PostgresSessionErasureRepository(database_sessions), authorization_service,
        audit_service, docente_of, retention_months=privacy_settings.session_retention_months)
    login_throttle = LoginThrottle(PostgresLoginAttemptRepository(database_sessions), get_login_limits())
    app.include_router(create_auth_router(authentication_service, user_repository,
                                          login_throttle=login_throttle))
    app.include_router(create_activity_router(
        activity_catalog,
        authentication_service,
        user_repository,
        recommendations=recommendation_config,
        expression_label=expression_label,
        on_change=emi_knowledge.invalidate,
    ))
    app.include_router(create_session_router(
        session_service,
        authentication_service,
        user_repository,
        student_repository,
        authorization=authorization_service,
        activities=activity_catalog,
        assignments=assignment_repository,
        commitments=commitment_service,
        protocols=protocol_service,
        questionnaires=questionnaire_service,
        privacy=session_privacy_service,
        audit=audit_service,
    ))
    exam_repository = PostgresExamRepository(database_sessions)
    # El predeterminado se lee en cada inicio de sesión: un cambio rige sin reiniciar.
    local_models = LocalModelService(PostgresLocalModelSettingsRepository(database_sessions),
                                     model_admission.evaluate)
    app.include_router(create_model_admin_router(local_models, authentication_service, user_repository))

    def resolve_guided_model() -> tuple[str, str]:
        """Modelo local predeterminado (o su respaldo) para las capturas de una sesión guiada."""
        choice = local_models.resolve()
        if not choice.admitted:
            raise RuntimeError("El modelo facial no está disponible en el servidor")
        return choice.model_id, EmotionModelCatalog().get(choice.model_id).version

    live_expression = get_live_expression_settings()
    guided_service = None
    if field_cipher is not None:
        guided_service = GuidedSessionService(
            PostgresGuidedSessionRepository(database_sessions, field_cipher), session_service,
            protocols=protocol_service.repository.get, stimuli=stimulus_service.repository.get,
            questionnaire_answered=questionnaire_service.answered,
            resolve_model=resolve_guided_model,
            # Cada cuadro se analiza en memoria con el modelo local y se descarta.
            assess_factory=lambda model_id: GuidedFrameAnalyzer(
                EmotionFrameAnalyzer(classifier=classifiers.get(model_id))).assess,
            audit=audit_service, session_access=session_access,
            calibration_seconds=live_expression.calibration_seconds,
            calibration_min_increase=live_expression.calibration_min_increase,
            exam_of=exam_repository.get, practice=get_practice_settings())
    app.include_router(create_guided_router(guided_service, authentication_service, user_repository,
                                            stimulus_image=stimulus_service.repository.get_image,
                                            decode_frame=decode_frame, capacity=analysis_capacity))
    # Validación de los modelos con voluntarios: protocolo de ejemplo (demo, PRUEBA-NN)
    # y exportación agregada para administración.
    practice_validation = None
    if guided_service is not None:
        practice_validation = PracticeValidationService(
            protocol_service.repository, session_service, guided_service.repository, audit_service,
            consent_mode, user_repository.is_test_account, user_repository.list_test_account_ids)
        protocol_service.validation_usable = practice_validation.usable
    app.include_router(create_practice_validation_router(practice_validation, authentication_service,
                                                         user_repository))
    # Examen simulado: el docente crea, confirma consentimientos, inicia y termina;
    # cada estación se une con el código y usa la pantalla de la persona.
    exam_service = ExamService(exam_repository, protocol_service.repository, session_service, audit_service,
                               commitment_service, stations=guided_service)
    app.include_router(create_exam_router(exam_service, authentication_service, user_repository))

    def actor_student_id(user) -> str | None:
        student = student_repository.get_by_user_id(user.id) if user.role is Role.STUDENT else None
        return student.id if student else None

    insights_service = None
    if guided_service is not None:
        insights_service = SessionInsightsService(
            session_service, guided_service.repository, protocols=protocol_service.repository.get,
            stimuli=stimulus_service.repository.get,
            questionnaire_responses=(questionnaire_service.responses.list_for_session
                                     if questionnaire_service.responses is not None else None),
            questionnaires=questionnaire_service.repository.get, authorization=authorization_service,
            actor_student_id=actor_student_id, audit=audit_service)
    app.include_router(create_insights_router(insights_service, authentication_service, user_repository))
    # Estadísticas agregadas: cuentan sesiones, no personas.
    statistics_service = None
    if insights_service is not None:
        def email_of(user_id: str) -> str | None:
            found = user_repository.get_by_id(user_id)
            return found.email if found else None

        statistics_service = SessionStatisticsService(session_service, insights_service, authorization_service,
                                                      actor_student_id, group_user_ids, email_of, audit_service)
    app.include_router(create_statistics_router(statistics_service, authentication_service, user_repository))
    report_service = None
    if insights_service is not None:
        report_service = ReportService(PostgresReportRepository(database_sessions, field_cipher), session_service,
                                       authorization_service, docente_of, insights_service, audit_service)
    app.include_router(create_report_router(report_service, authentication_service, user_repository))
    # Aplicativo Android: consulta sesiones, reportes y estadísticas con los mismos
    # servicios y reglas que la web; no conduce sesiones (docs/mobile-api.md).
    app.include_router(create_mobile_router(
        MobileAuthService(PostgresMobileSessionRepository(database_sessions), authentication_service,
                          user_repository, audit_service, login_throttle),
        user_repository,
        audit=audit_service,
        visible_sessions=create_visible_sessions(session_service, student_repository, assignment_repository,
                                                 authorization_service),
        insights=insights_service,
        reports=report_service,
        statistics=statistics_service,
        production=web_settings.production,
        api_version=__version__,
        min_app_version=get_mobile_min_app_version(),
    ))
    app.include_router(create_analysis_router(
        session_service,
        activity_catalog,
        authentication_service,
        user_repository,
        student_repository,
        lambda activity: BrowserActivityService(
            activity,
            EmotionFrameAnalyzer(classifier=classifiers.get("ferplus_onnx")),
            PoseService(),
        ),
        authorization=authorization_service,
        model_processor_factory=lambda activity, model_id: BrowserActivityService(
            activity,
            EmotionFrameAnalyzer(classifier=classifiers.get(model_id)),
            PoseService(),
        ),
        model_admission=model_admission.evaluate,
        emotion_analyzer_factory=lambda model_id: EmotionFrameAnalyzer(
            classifier=classifiers.get(model_id),
        ),
        adaptive_processor_factory=lambda activity, analyzer, emotion: BrowserActivityService(
            activity, analyzer, PoseService(), initial_emotion=emotion,
        ),
        live_settings=get_live_expression_settings(),
        expression_info=expression_info_for,
        recommendations=recommendation_repository,
        capacity=analysis_capacity,
        local_models=local_models,
        questionnaire_ready=questionnaire_service.pre_completed,
    ))
    chat_gateway = None
    if chat_settings.webhook_key:
        chat_gateway = N8nWebhookChatGateway(chat_settings.webhook_url, chat_settings.webhook_key,
                                             chat_settings.timeout_seconds)
    else:
        # El resto de la API arranca igual; POST /chat responde 503.
        logger.warning("N8N_WEBHOOK_KEY está vacía: Emi responderá 503 hasta configurarla")
    chat_service = ChatService(PostgresChatRepository(database_sessions), chat_gateway, chat_settings,
                               knowledge=emi_knowledge.get)
    app.include_router(create_chat_router(chat_service, authentication_service, user_repository))
else:
    app.include_router(create_identity_router(None, None, None, None))
    app.include_router(create_auth_router(None, None))
    app.include_router(create_activity_router(None, None, None))
    app.include_router(create_session_router(None, None, None, None))
    app.include_router(create_analysis_router(None, None, None, None, None, None))
    app.include_router(create_chat_router(None, None, None))
    app.include_router(create_mobile_router(None, None, production=web_settings.production, api_version=__version__,
                                            min_app_version=get_mobile_min_app_version()))
    app.include_router(create_expression_router(None, None, None))
    app.include_router(create_recommendation_router(None, None, None))
    app.include_router(create_model_admin_router(None, None, None))
    app.include_router(create_privacy_router(None, None, None, None))
    app.include_router(create_stimulus_router(None, None, None, None))
    app.include_router(create_user_image_router(None, None, None))
    app.include_router(create_questionnaire_router(None, None, None))
    app.include_router(create_guided_router(None, None, None))
    app.include_router(create_insights_router(None, None, None))
    app.include_router(create_statistics_router(None, None, None))
    app.include_router(create_exam_router(None, None, None))
    app.include_router(create_report_router(None, None, None))


def run_retention() -> None:
    """Elimina sesiones vencidas (SESSION_RETENTION_MONTHS), imágenes propias que
    nadie revisó (IMAGE_REVIEW_DAYS, con aviso previo) y auditoría antigua
    (AUDIT_RETENTION_MONTHS). La auditoría no guarda contenido."""
    if session_privacy_service is not None:
        try:
            session_privacy_service.purge_expired()
        except SQLAlchemyError:
            logger.exception("No se pudo aplicar la retención de sesiones")
    if user_image_service is not None:
        try:
            user_image_service.expire_pending()  # IMAGE_REVIEW_DAYS sin revisión
        except SQLAlchemyError:
            logger.exception("No se pudo aplicar el vencimiento de imágenes sin revisar")
    if audit_service is not None:
        try:
            audit_service.purge_expired(privacy_settings.audit_retention_months)
        except SQLAlchemyError:
            logger.exception("No se pudo aplicar la retención de la auditoría")


async def _retention_loop() -> None:
    while True:
        await asyncio.sleep(RETENTION_INTERVAL_SECONDS)
        await asyncio.to_thread(run_retention)


@app.on_event("startup")
async def startup_event():
    if DATABASE_URL and JWT_SECRET_KEY and consent_mode == "demo":
        consent_policy_service.ensure_demo_policy(BASE_DIR / "docs" / "consent-demo.md")
    if chat_service is not None:
        try:
            chat_service.purge_expired()  # Retención del historial de Emi.
        except SQLAlchemyError:
            logger.exception("No se pudo aplicar la retención del historial de Emi")
    global retention_task
    if session_privacy_service is not None or audit_service is not None or user_image_service is not None:
        # Al arrancar y luego una vez al día.
        await asyncio.to_thread(run_retention)
        retention_task = asyncio.create_task(_retention_loop())


@app.on_event("shutdown")
async def shutdown_event():
    if retention_task is not None:
        retention_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await retention_task


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


