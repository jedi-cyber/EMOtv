from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, String, Integer, LargeBinary, Text, UniqueConstraint, Index, JSON, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa compartida por los modelos persistentes de EMOtv."""


class ActivityRecord(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint("duration_seconds > 0", name="ck_activities_duration_positive"),
        CheckConstraint("repetitions >= 1", name="ck_activities_repetitions_positive"),
        CheckConstraint("required_posture IN ('arms_up','arms_open','arms_forward','hands_on_hips','squat')", name="ck_activities_posture_valid"),
    )
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    required_posture: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class SessionRecord(Base):
    """Representación SQLAlchemy de una sesión emocional."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('created', 'in_progress', 'recognized', 'completed', 'cancelled')",
            name="ck_sessions_state_valid",
        ),
        CheckConstraint(
            "emotion_confidence IS NULL OR "
            "(emotion_confidence >= 0 AND emotion_confidence <= 1)",
            name="ck_sessions_emotion_confidence_range",
        ),
        CheckConstraint(
            "exercise_duration_seconds IS NULL OR exercise_duration_seconds >= 0",
            name="ck_sessions_exercise_duration_non_negative",
        ),
        CheckConstraint(
            "(initial_emotion IS NULL AND emotion_confidence IS NULL) OR "
            "(initial_emotion IS NOT NULL AND emotion_confidence IS NOT NULL)",
            name="ck_sessions_emotion_fields_together",
        ),
        CheckConstraint(
            "(state IN ('completed', 'cancelled') AND completed_at IS NOT NULL) OR "
            "(state IN ('created', 'in_progress', 'recognized') AND completed_at IS NULL)",
            name="ck_sessions_completion_timestamp",
        ),
        CheckConstraint(
            "state <> 'completed' OR protocol_id IS NOT NULL OR "
            "(initial_emotion IS NOT NULL AND exercise_result IS NOT NULL AND "
            "(exercise_result <> 'completed' OR "
            "(activity_id IS NOT NULL AND exercise_duration_seconds IS NOT NULL)))",
            name="ck_sessions_completed_result",
        ),
        CheckConstraint(
            "(recognized_at IS NULL OR (initial_emotion IS NOT NULL AND recognized_at >= started_at)) AND "
            "(state <> 'recognized' OR recognized_at IS NOT NULL)",
            name="ck_sessions_recognition",
        ),
        CheckConstraint(
            "(emotion_model_id IS NULL AND emotion_model_version IS NULL) OR "
            "(emotion_model_id IS NOT NULL AND emotion_model_version IS NOT NULL)",
            name="ck_sessions_emotion_model_fields_together",
        ),
        CheckConstraint(
            "(exercise_steps_completed IS NULL AND exercise_steps_total IS NULL "
            "AND exercise_repetitions IS NULL) OR "
            "(exercise_repetitions >= 1 AND exercise_steps_total >= exercise_repetitions "
            "AND exercise_steps_completed >= 0 "
            "AND exercise_steps_completed <= exercise_steps_total)",
            name="ck_sessions_exercise_progress",
        ),
        CheckConstraint(
            "session_type IN ('propia', 'adulto', 'infantil')",
            name="ck_sessions_session_type",
        ),
        CheckConstraint(
            "(deletion_requested_at IS NULL AND deletion_requested_by_user_id IS NULL) OR "
            "(deletion_requested_at IS NOT NULL AND deletion_requested_by_user_id IS NOT NULL)",
            name="ck_sessions_deletion_request",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    initial_emotion: Mapped[str | None] = mapped_column(String(64), nullable=True)
    emotion_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    emotion_model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    emotion_model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recognized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exercise_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exercise_duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    student_id: Mapped[str | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    exercise_steps_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exercise_steps_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exercise_repetitions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_type: Mapped[str] = mapped_column(String(32), nullable=False, default="propia",
                                              server_default="propia")
    # Cuenta que conduce la sesión.
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # Versión del protocolo aplicado; un protocolo usado no se borra ni se edita.
    protocol_id: Mapped[str | None] = mapped_column(
        ForeignKey("protocols.id", ondelete="RESTRICT"), nullable=True, index=True)
    # Versiones exactas de los cuestionarios previo y posterior.
    pre_questionnaire_id: Mapped[str | None] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="RESTRICT"), nullable=True, index=True)
    post_questionnaire_id: Mapped[str | None] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="RESTRICT"), nullable=True, index=True)
    # Código aleatorio que quien conduce anota en el formato firmado (S-XXXXXX).
    code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    authorization_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Examen simulado al que pertenece la sesión; un examen con sesiones no se borra.
    exam_id: Mapped[str | None] = mapped_column(
        ForeignKey("exams.id", ondelete="RESTRICT"), nullable=True, index=True)


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(
        "role IN ('student','psychologist','admin','superadmin')", name="ck_users_role_valid"
    ),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Cuenta de voluntario (PRUEBA-NN): la única que borra scripts/testdata/delete_test_data.py.
    is_test_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Último restablecimiento hecho por otra cuenta: muestra un aviso al siguiente ingreso.
    password_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PsychologistAssignmentRecord(Base):
    """Usuario (perfil students) que pertenece al grupo de un docente.

    Un usuario tiene un solo docente (uq_psychologist_assignments_student_id).
    """

    __tablename__ = "psychologist_assignments"
    __table_args__ = (UniqueConstraint("student_id", name="uq_psychologist_assignments_student_id"),)
    psychologist_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class LoginAttemptRecord(Base):
    """Intento de inicio de sesión; el correo se guarda solo como SHA-256."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_ip_created_at", "ip", "created_at"),
        Index("ix_login_attempts_account_created_at", "email_hash", "ip", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)


class MobileSessionRecord(Base):
    """Sesión del aplicativo móvil: el token de renovación vigente y el anterior
    se guardan solo como SHA-256. Sin datos del dispositivo ni IP."""

    __tablename__ = "mobile_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_mobile_sessions_refresh_token_hash"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # El anterior a la última renovación: si vuelve a usarse, la sesión se revoca.
    previous_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StudentRecord(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    student_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class ConsentRecordModel(Base):
    __tablename__ = "consents"
    __table_args__ = (CheckConstraint(
        "revoked_at IS NULL OR revoked_at >= granted_at",
        name="ck_consents_revocation_valid",
    ),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentPolicyRecord(Base):
    __tablename__ = "consent_policies"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_consent_policies_code_version"),
        Index("uq_consent_policies_single_active", "is_active", unique=True,
              postgresql_where=text("is_active = true"), sqlite_where=text("is_active = 1")),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(String(16000), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ExpressionInfoRecord(Base):
    """Texto educativo por expresión, revisable por Psicología."""

    __tablename__ = "expression_info"
    __table_args__ = (
        CheckConstraint("review_status IN ('draft', 'reviewed')", name="ck_expression_info_review_status"),
        CheckConstraint(
            "(review_status = 'draft' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL) OR "
            "(review_status = 'reviewed' AND reviewed_at IS NOT NULL)",
            name="ck_expression_info_review_fields",
        ),
    )
    expression_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    label_es: Mapped[str] = mapped_column(String(60), nullable=False)
    what_it_is: Mapped[str] = mapped_column(String(1200), nullable=False)
    why_it_occurs: Mapped[str] = mapped_column(String(1200), nullable=False)
    facial_cues: Mapped[str] = mapped_column(String(1200), nullable=False)
    practice_tip: Mapped[str] = mapped_column(String(1200), nullable=False)
    limitation_note: Mapped[str] = mapped_column(String(1200), nullable=False)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StimulusRecord(Base):
    """Imagen del banco de estímulos, nunca una foto de una persona evaluada. La
    imagen se guarda reescrita, sin metadatos."""

    __tablename__ = "stimuli"
    __table_args__ = (
        CheckConstraint("kind IN ('emotional', 'abstract')", name="ck_stimuli_kind"),
        CheckConstraint("intensity IN ('mild', 'moderate')", name="ck_stimuli_intensity"),
        CheckConstraint("scope IN ('group', 'institution', 'user')", name="ck_stimuli_scope"),
        CheckConstraint("min_age BETWEEN 1 AND 99", name="ck_stimuli_min_age"),
        CheckConstraint(
            "(kind = 'emotional' AND (expected_expression IS NOT NULL OR scope = 'user')) OR "
            "(kind = 'abstract' AND expected_expression IS NULL)",
            name="ck_stimuli_expected_expression",
        ),
        CheckConstraint(
            "(approved_at IS NULL AND approved_by_user_id IS NULL) OR "
            "(approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="ck_stimuli_approval",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_expression: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intensity: Mapped[str] = mapped_column(String(16), nullable=False)
    min_age: Mapped[int] = mapped_column(Integer, nullable=False)
    origin: Mapped[str] = mapped_column(String(500), nullable=False)
    license: Mapped[str] = mapped_column(String(300), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    possible_person: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                                  server_default=text("false"))
    upload_batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    expiry_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserNoticeRecord(Base):
    """Avisos para una cuenta (imágenes eliminadas o por vencer, protocolos que
    necesitan una imagen). Se borran con la cuenta."""

    __tablename__ = "user_notices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(800), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProtocolRecord(Base):
    """Una versión de un protocolo; las de un mismo protocolo comparten family_id."""

    __tablename__ = "protocols"
    __table_args__ = (
        UniqueConstraint("family_id", "version", name="uq_protocols_family_version"),
        CheckConstraint("version >= 1", name="ck_protocols_version"),
        CheckConstraint(
            "(approved_at IS NULL AND approved_by_user_id IS NULL) OR "
            "(approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name="ck_protocols_approval",
        ),
        CheckConstraint("kind IN ('practice', 'exam')", name="ck_protocols_kind"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    for_children: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Cuestionario previo opcional y, solo si hay previo, uno posterior.
    pre_questionnaire_id: Mapped[str | None] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="RESTRICT"), nullable=True)
    post_questionnaire_id: Mapped[str | None] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Práctica (estímulos y cuestionarios) o examen simulado (sin pasos).
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="practice",
                                      server_default="practice")


class ExamRecord(Base):
    """Examen simulado: agrupa una sesión por estación. No guarda personas."""

    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("join_code", name="uq_exams_join_code"),
        CheckConstraint("state IN ('open', 'in_progress', 'closed')", name="ck_exams_state"),
        CheckConstraint("state <> 'in_progress' OR started_at IS NOT NULL", name="ck_exams_in_progress_started"),
        CheckConstraint("state <> 'open' OR started_at IS NULL", name="ck_exams_open_not_started"),
        CheckConstraint("(state = 'closed') = (closed_at IS NOT NULL)", name="ck_exams_closed"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    protocol_id: Mapped[str] = mapped_column(
        ForeignKey("protocols.id", ondelete="RESTRICT"), nullable=False, index=True)
    # Código que cada estación escribe para unirse.
    join_code: Mapped[str] = mapped_column(String(8), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuestionnaireRecord(Base):
    """Una versión de un cuestionario; las de uno mismo comparten family_id.
    questions guarda las preguntas en orden (JSON); no es contenido de una
    sesión y no se cifra."""

    __tablename__ = "questionnaires"
    __table_args__ = (
        UniqueConstraint("family_id", "version", name="uq_questionnaires_family_version"),
        CheckConstraint("version >= 1", name="ck_questionnaires_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    instructions: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    questions: Mapped[list] = mapped_column(JSON, nullable=False)
    shared_with_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    copied_from_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuestionnaireResponseRecord(Base):
    """Respuestas de una sesión, cifradas con SENSITIVE_DATA_KEY. La retención y
    la eliminación de la sesión las incluyen."""

    __tablename__ = "questionnaire_responses"
    __table_args__ = (
        UniqueConstraint("session_id", "moment", name="uq_questionnaire_responses_session_moment"),
        CheckConstraint("moment IN ('pre', 'post')", name="ck_questionnaire_responses_moment"),
        CheckConstraint("entry_mode IN ('participant', 'conductor')", name="ck_questionnaire_responses_entry_mode"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    questionnaire_id: Mapped[str] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="RESTRICT"), nullable=False, index=True)
    moment: Mapped[str] = mapped_column(String(8), nullable=False)
    answers_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    entry_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


PROTOCOL_STEP_KIND = "kind IN ('stimulus', 'practice')"
PROTOCOL_STEP_STIMULUS = "kind = 'practice' OR stimulus_id IS NOT NULL"
PROTOCOL_STEP_PRACTICE = (
    "(kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0)")


class ProtocolStepRecord(Base):
    __tablename__ = "protocol_steps"
    __table_args__ = (
        UniqueConstraint("protocol_id", "position", name="uq_protocol_steps_position"),
        CheckConstraint("exposure_seconds BETWEEN 1 AND 120", name="ck_protocol_steps_exposure"),
        CheckConstraint("capture_after_seconds >= 0 AND capture_after_seconds <= exposure_seconds",
                        name="ck_protocol_steps_capture"),
        CheckConstraint(PROTOCOL_STEP_KIND, name="ck_protocol_steps_kind"),
        CheckConstraint(PROTOCOL_STEP_STIMULUS, name="ck_protocol_steps_stimulus"),
        CheckConstraint(PROTOCOL_STEP_PRACTICE, name="ck_protocol_steps_practice"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    protocol_id: Mapped[str] = mapped_column(
        ForeignKey("protocols.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nulo solo en una práctica sin ilustración.
    stimulus_id: Mapped[str | None] = mapped_column(
        ForeignKey("stimuli.id", ondelete="RESTRICT"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="stimulus",
                                      server_default=text("'stimulus'"))
    target_expression: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hold_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exposure_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    capture_after_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    record_verbal_response: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shown_before_analyzer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                                        server_default=text("false"))


class GuidedRunRecord(Base):
    """Estado de una sesión guiada. La base neutral no se guarda: vive en memoria."""

    __tablename__ = "guided_runs"
    __table_args__ = (
        CheckConstraint("phase IN ('pre_questionnaire', 'before_analyzer', 'calibration', "
                        "'stimuli', 'post_questionnaire', 'live', 'waiting', 'ready', 'exam', 'finished', 'stopped')",
                        name="ck_guided_runs_phase"),
        CheckConstraint("(phase = 'stopped') = (stop_reason IS NOT NULL)", name="ck_guided_runs_stop_reason"),
        CheckConstraint("stop_reason IS NULL OR stop_reason IN ('participant', 'guardian', 'conductor')",
                        name="ck_guided_runs_stop_reason_value"),
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_capture_due: Mapped[float | None] = mapped_column(Float, nullable=True)
    steps_log: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    calibrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)


class ExpressionCaptureRecord(Base):
    """Captura: expresión estimada, distribución y calidad. Nunca la imagen ni
    datos de identidad. stimulus_id es nulo en el registro sin protocolo."""

    __tablename__ = "expression_captures"
    __table_args__ = (
        CheckConstraint("quality IN ('good', 'flagged')", name="ck_expression_captures_quality"),
        CheckConstraint("(emotion IS NULL) = (confidence IS NULL)", name="ck_expression_captures_emotion"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
                        name="ck_expression_captures_confidence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    emotion_model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    emotion_model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    emotion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    distribution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    calibrated_emotion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    quality_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    stimulus_id: Mapped[str | None] = mapped_column(ForeignKey("stimuli.id", ondelete="RESTRICT"), nullable=True,
                                                    index=True)
    seconds_since_stimulus: Mapped[float] = mapped_column(Float, nullable=False)


class SessionMarkerRecord(Base):
    """Marcadores con hora de quien conduce la sesión; la nota va cifrada."""

    __tablename__ = "session_markers"
    __table_args__ = (
        CheckConstraint("kind IN ('distracted', 'laughed', 'asked_to_stop', 'cried', 'note')",
                        name="ck_session_markers_kind"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    note_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)


class VerbalResponseRecord(Base):
    """Lo que la persona dice ver en una imagen abstracta, cifrado."""

    __tablename__ = "verbal_responses"
    __table_args__ = (UniqueConstraint("session_id", "step_index", name="uq_verbal_responses_session_step"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    stimulus_id: Mapped[str] = mapped_column(ForeignKey("stimuli.id", ondelete="RESTRICT"), nullable=False)
    text_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)


class PracticeResultRecord(Base):
    """Resultado de un ejercicio de práctica. Nunca imágenes, niveles por cuadro
    ni la base neutral."""

    __tablename__ = "practice_results"
    __table_args__ = (
        UniqueConstraint("session_id", "step_index", name="uq_practice_results_session_step"),
        CheckConstraint("outcome IN ('achieved', 'timed_out', 'skipped', 'stopped')",
                        name="ck_practice_results_outcome"),
        CheckConstraint("(outcome = 'achieved') = (seconds_to_achieve IS NOT NULL)",
                        name="ck_practice_results_achieved"),
        CheckConstraint("peak_level >= 0 AND peak_level <= 1", name="ck_practice_results_peak"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    target_expression: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    seconds_to_achieve: Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_level: Mapped[float] = mapped_column(Float, nullable=False)
    relative_to_calibration: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback_visible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    analyzed_frames: Mapped[int] = mapped_column(Integer, nullable=False)
    flagged_frames: Mapped[int] = mapped_column(Integer, nullable=False)
    emotion_model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    emotion_model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionReportRecord(Base):
    """Versión del reporte de una sesión; el texto va cifrado."""

    __tablename__ = "session_reports"
    __table_args__ = (
        UniqueConstraint("family_id", "version", name="uq_session_reports_family_version"),
        CheckConstraint("status IN ('draft', 'submitted', 'changes_requested', 'approved')",
                        name="ck_session_reports_status"),
        CheckConstraint("(status = 'approved') = (approved_at IS NOT NULL)", name="ck_session_reports_approval"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    narrative_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportCommentRecord(Base):
    """Comentario del docente sobre una sección del reporte; cifrado."""

    __tablename__ = "report_comments"
    __table_args__ = (
        CheckConstraint("section IN ('timeline', 'metrics', 'questionnaires', 'narrative', 'general')",
                        name="ck_report_comments_section"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("session_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(24), nullable=False)
    text_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    author_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportEventRecord(Base):
    """Historial del reporte, sin contenido."""

    __tablename__ = "report_events"
    __table_args__ = (
        CheckConstraint("action IN ('created', 'edited', 'submitted', 'commented', 'returned', 'approved', "
                        "'closed', 'new_version', 'printed')", name="ck_report_events_action"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("session_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommitmentAcceptanceRecord(Base):
    """Aceptación del compromiso de confidencialidad (kind=commitment) o del
    aviso reforzado sobre datos de menores (kind=child_notice), con su versión."""

    __tablename__ = "commitment_acceptances"
    __table_args__ = (
        CheckConstraint("kind IN ('commitment', 'child_notice')", name="ck_commitment_acceptances_kind"),
        UniqueConstraint("user_id", "kind", "version", name="uq_commitment_acceptances_user_kind_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AccessAuditRecord(Base):
    """Auditoría de accesos: sin contenido ni imágenes. La API no la edita ni la borra."""

    __tablename__ = "access_audit"
    __table_args__ = (
        CheckConstraint("result IN ('success', 'denied', 'failure')", name="ck_access_audit_result"),
        Index("ix_access_audit_resource", "resource_type", "resource_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # Sin clave foránea: la auditoría se conserva aunque la cuenta se elimine.
    actor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)


class SessionDeletionRecord(Base):
    """Acta de eliminación de una sesión: código de la sesión, fecha, registros
    por tipo y verificación. Sin datos personales. counts es
    {"sessions": 1, "expression_captures": n, ...}."""

    __tablename__ = "session_deletion_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_code: Mapped[str] = mapped_column(String(16), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    executed_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    requested_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LocalModelSettingsRecord(Base):
    """Configuración de los modelos locales de expresión: una sola fila (id = 1)."""

    __tablename__ = "local_model_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_local_model_settings_single_row"),
        CheckConstraint(
            "default_model_id IN ('hsemotion_enet_b0_8_best_afew', 'ferplus_onnx')",
            name="ck_local_model_settings_default_model",
        ),
        CheckConstraint(
            "(fallback_model_id IS NULL AND fallback_at IS NULL) OR "
            "(fallback_model_id IS NOT NULL AND fallback_at IS NOT NULL)",
            name="ck_local_model_settings_fallback_fields",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    changed_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fallback_model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fallback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmotionActivityRecommendationRecord(Base):
    """Actividad recomendada para una expresión; menor priority = primera opción."""

    __tablename__ = "emotion_activity_recommendations"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="ck_emotion_activity_recommendations_priority"),
    )
    expression_key: Mapped[str] = mapped_column(
        ForeignKey("expression_info.expression_key", ondelete="CASCADE"), primary_key=True
    )
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)


class ChatConversationRecord(Base):
    """Conversación de un usuario con Emi. Nunca se envía a n8n."""

    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("ix_chat_conversations_user_last_message", "user_id", "last_message_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChatMessageRecord(Base):
    """Mensaje de una conversación. in_scope es nulo mientras n8n no responde."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_chat_messages_role_valid"),
        Index("ix_chat_messages_conversation_id", "conversation_id", "id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    in_scope: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ChatRejectionCountRecord(Base):
    """Rechazos de Emi por categoría, sin el texto de las preguntas."""

    __tablename__ = "chat_rejection_counts"
    __table_args__ = (
        CheckConstraint("count >= 0", name="ck_chat_rejection_counts_non_negative"),
    )
    category: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
