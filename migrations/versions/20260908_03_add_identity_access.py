"""Add users, students, consents and session ownership."""
from alembic import op
import sqlalchemy as sa

revision = "20260908_03"
down_revision = "20260908_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('student','psychologist','admin')", name="ck_users_role_valid"))
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table("students",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("student_code", sa.String(64), nullable=False, unique=True))
    op.create_table("consents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("student_id", sa.String(64), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= granted_at", name="ck_consents_revocation_valid"))
    op.create_index("ix_consents_student_id", "consents", ["student_id"])
    op.add_column("sessions", sa.Column("student_id", sa.String(64), nullable=True))
    op.create_foreign_key("fk_sessions_student_id", "sessions", "students", ["student_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_sessions_student_id", "sessions", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_student_id", table_name="sessions")
    op.drop_constraint("fk_sessions_student_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "student_id")
    op.drop_index("ix_consents_student_id", table_name="consents")
    op.drop_table("consents")
    op.drop_table("students")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_table("users")
