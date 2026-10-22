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
            "state <> 'completed' OR "
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
            "session_type IN ('propia', 'participante_adulto', 'participante_infantil')",
            name="ck_sessions_session_type",
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
    # Cuenta que conduce la sesión y participante analizado (nulo en una sesión propia).
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    participant_id: Mapped[str | None] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=True, index=True)
    # Versión del protocolo aplicado; un protocolo usado no se borra ni se edita.
    protocol_id: Mapped[str | None] = mapped_column(
        ForeignKey("protocols.id", ondelete="RESTRICT"), nullable=True, index=True)


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


class ParticipantRecord(Base):
    """Participante sin cuenta, nombre, DNI ni foto: solo un código aleatorio.

    notes_encrypted guarda las notas libres cifradas con SENSITIVE_DATA_KEY.
    """

    __tablename__ = "participants"
    __table_args__ = (
        CheckConstraint("kind IN ('adult', 'child')", name="ck_participants_kind"),
        CheckConstraint(
            "(deletion_requested_at IS NULL AND deletion_requested_by_user_id IS NULL) OR "
            "(deletion_requested_at IS NOT NULL AND deletion_requested_by_user_id IS NOT NULL)",
            name="ck_participants_deletion_request",
        ),
        CheckConstraint(
            "age_years IS NULL OR (kind = 'adult' AND age_years BETWEEN 18 AND 120) OR "
            "(kind = 'child' AND age_years BETWEEN 1 AND 17)",
            name="ck_participants_age_matches_kind",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    registered_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    notes_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    authorization_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ParticipantAuthorizationRecord(Base):
    """Formato firmado en papel: versión, fecha y lo que autoriza. Sin nombres
    ni datos de quien firma."""

    __tablename__ = "participant_authorizations"
    __table_args__ = (
        CheckConstraint("grantor IN ('participant', 'guardian')", name="ck_participant_authorizations_grantor"),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL AND revoked_party IS NULL "
            "AND revoked_scope IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL "
            "AND revoked_party IN ('participant', 'guardian') "
            "AND revoked_scope IN ('participation', 'camera', 'assent'))",
            name="ck_participant_authorizations_revocation",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True)
    form_version: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_on: Mapped[date] = mapped_column(Date, nullable=False)
    grantor: Mapped[str] = mapped_column(String(16), nullable=False)
    participation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    camera: Mapped[bool] = mapped_column(Boolean, nullable=False)
    child_assent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recorded_by_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked_party: Mapped[str | None] = mapped_column(String(16), nullable=True)
    revoked_scope: Mapped[str | None] = mapped_column(String(16), nullable=True)


class StimulusRecord(Base):
    """Imagen del banco de estímulos, nunca una foto de un participante. La
    imagen se guarda reescrita, sin metadatos."""

    __tablename__ = "stimuli"
    __table_args__ = (
        CheckConstraint("kind IN ('emotional', 'abstract')", name="ck_stimuli_kind"),
        CheckConstraint("intensity IN ('mild', 'moderate')", name="ck_stimuli_intensity"),
        CheckConstraint("scope IN ('group', 'institution')", name="ck_stimuli_scope"),
        CheckConstraint("min_age BETWEEN 1 AND 99", name="ck_stimuli_min_age"),
        CheckConstraint(
            "(kind = 'emotional' AND expected_expression IS NOT NULL) OR "
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
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    for_children: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Cuestionario previo opcional (P6A); mientras no exista ese módulo queda nulo.
    pre_questionnaire_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProtocolStepRecord(Base):
    __tablename__ = "protocol_steps"
    __table_args__ = (
        UniqueConstraint("protocol_id", "position", name="uq_protocol_steps_position"),
        CheckConstraint("exposure_seconds BETWEEN 1 AND 120", name="ck_protocol_steps_exposure"),
        CheckConstraint("capture_after_seconds >= 0 AND capture_after_seconds <= exposure_seconds",
                        name="ck_protocol_steps_capture"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    protocol_id: Mapped[str] = mapped_column(
        ForeignKey("protocols.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    stimulus_id: Mapped[str] = mapped_column(
        ForeignKey("stimuli.id", ondelete="RESTRICT"), nullable=False, index=True)
    exposure_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    capture_after_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    record_verbal_response: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


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


class ParticipantDeletionRecord(Base):
    """Acta de eliminación a pedido: código, fecha, cantidades y verificación.

    Sin datos personales. counts es {"participants": n, "sessions": n, ...}.
    """

    __tablename__ = "participant_deletion_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    participant_code: Mapped[str] = mapped_column(String(16), nullable=False)
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
