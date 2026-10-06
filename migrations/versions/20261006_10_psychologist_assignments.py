"""Asignación de estudiantes a psicólogos."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_10"
down_revision = "20261006_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "psychologist_assignments",
        sa.Column("psychologist_user_id", sa.String(64),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(64),
                  sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(64),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.PrimaryKeyConstraint("psychologist_user_id", "student_id",
                                name="pk_psychologist_assignments"),
    )
    op.create_index("ix_psychologist_assignments_psychologist_user_id",
                    "psychologist_assignments", ["psychologist_user_id"])


def downgrade() -> None:
    op.drop_table("psychologist_assignments")
