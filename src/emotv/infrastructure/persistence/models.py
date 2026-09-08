from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa compartida por los modelos persistentes de EMOtv."""


class SessionRecord(Base):
    """Representación SQLAlchemy de una sesión emocional."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('created', 'in_progress', 'completed', 'cancelled')",
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
            "(state IN ('created', 'in_progress') AND completed_at IS NULL)",
            name="ck_sessions_completion_timestamp",
        ),
        CheckConstraint(
            "state <> 'completed' OR "
            "(initial_emotion IS NOT NULL AND activity_id IS NOT NULL AND "
            "exercise_result IS NOT NULL AND exercise_duration_seconds IS NOT NULL)",
            name="ck_sessions_completed_result",
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
    exercise_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exercise_duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    student_id: Mapped[str | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(
        "role IN ('student','psychologist','admin')", name="ck_users_role_valid"
    ),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
