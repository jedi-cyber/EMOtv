"""Record the facial model used by an emotional session."""
from alembic import op
import sqlalchemy as sa

revision = "20260916_05"
down_revision = "20260915_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("emotion_model_id", sa.String(128), nullable=True))
    op.add_column("sessions", sa.Column("emotion_model_version", sa.String(128), nullable=True))
    op.create_check_constraint(
        "ck_sessions_emotion_model_fields_together", "sessions",
        "(emotion_model_id IS NULL AND emotion_model_version IS NULL) OR "
        "(emotion_model_id IS NOT NULL AND emotion_model_version IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_emotion_model_fields_together", "sessions", type_="check")
    op.drop_column("sessions", "emotion_model_version")
    op.drop_column("sessions", "emotion_model_id")
