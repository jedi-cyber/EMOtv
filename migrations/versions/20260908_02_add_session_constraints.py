"""Add domain constraints to sessions.

Revision ID: 20260908_02
Revises: 20260908_01
Create Date: 2026-09-08
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260908_02"
down_revision: str | None = "20260908_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_sessions_state_valid",
        "sessions",
        "state IN ('created', 'in_progress', 'completed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_sessions_emotion_confidence_range",
        "sessions",
        "emotion_confidence IS NULL OR "
        "(emotion_confidence >= 0 AND emotion_confidence <= 1)",
    )
    op.create_check_constraint(
        "ck_sessions_exercise_duration_non_negative",
        "sessions",
        "exercise_duration_seconds IS NULL OR exercise_duration_seconds >= 0",
    )
    op.create_check_constraint(
        "ck_sessions_emotion_fields_together",
        "sessions",
        "(initial_emotion IS NULL AND emotion_confidence IS NULL) OR "
        "(initial_emotion IS NOT NULL AND emotion_confidence IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_sessions_completion_timestamp",
        "sessions",
        "(state IN ('completed', 'cancelled') AND completed_at IS NOT NULL) OR "
        "(state IN ('created', 'in_progress') AND completed_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_sessions_completed_result",
        "sessions",
        "state <> 'completed' OR "
        "(initial_emotion IS NOT NULL AND activity_id IS NOT NULL AND "
        "exercise_result IS NOT NULL AND exercise_duration_seconds IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_sessions_completed_result",
        "sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_sessions_completion_timestamp",
        "sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_sessions_emotion_fields_together",
        "sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_sessions_exercise_duration_non_negative",
        "sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_sessions_emotion_confidence_range",
        "sessions",
        type_="check",
    )
    op.drop_constraint("ck_sessions_state_valid", "sessions", type_="check")
