"""Create sessions table.

Revision ID: 20260908_01
Revises:
Create Date: 2026-09-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260908_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initial_emotion", sa.String(length=64), nullable=True),
        sa.Column("emotion_confidence", sa.Float(), nullable=True),
        sa.Column("activity_id", sa.String(length=128), nullable=True),
        sa.Column("exercise_result", sa.String(length=32), nullable=True),
        sa.Column("exercise_duration_seconds", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_started_at", "sessions", ["started_at"])
    op.create_index("ix_sessions_state", "sessions", ["state"])


def downgrade() -> None:
    op.drop_index("ix_sessions_state", table_name="sessions")
    op.drop_index("ix_sessions_started_at", table_name="sessions")
    op.drop_table("sessions")
