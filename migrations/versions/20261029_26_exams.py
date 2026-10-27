"""Examen simulado como tipo de protocolo.

- protocols.kind: 'practice' (todas las versiones existentes) o 'exam'.
- exams: sesión grupal que el docente crea, con su código de unión, la
  última confirmación de consentimientos y las horas de inicio y término.
  No guarda personas.
- sessions.exam_id: examen al que pertenece la sesión de una estación.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_26"
down_revision = "20261028_25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("protocols", sa.Column("kind", sa.String(16), nullable=False, server_default="practice"))
    op.create_check_constraint("ck_protocols_kind", "protocols", "kind IN ('practice', 'exam')")
    op.create_table(
        "exams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("protocol_id", sa.String(36), sa.ForeignKey("protocols.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("join_code", sa.String(8), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("join_code", name="uq_exams_join_code"),
        sa.CheckConstraint("state IN ('open', 'in_progress', 'closed')", name="ck_exams_state"),
        sa.CheckConstraint("state <> 'in_progress' OR started_at IS NOT NULL", name="ck_exams_in_progress_started"),
        sa.CheckConstraint("state <> 'open' OR started_at IS NULL", name="ck_exams_open_not_started"),
        sa.CheckConstraint("(state = 'closed') = (closed_at IS NOT NULL)", name="ck_exams_closed"),
    )
    op.create_index("ix_exams_owner_user_id", "exams", ["owner_user_id"])
    op.create_index("ix_exams_protocol_id", "exams", ["protocol_id"])
    op.add_column("sessions", sa.Column("exam_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_sessions_exam_id", "sessions", "exams", ["exam_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_sessions_exam_id", "sessions", ["exam_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_exam_id", table_name="sessions")
    op.drop_constraint("fk_sessions_exam_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "exam_id")
    op.drop_index("ix_exams_protocol_id", table_name="exams")
    op.drop_index("ix_exams_owner_user_id", table_name="exams")
    op.drop_table("exams")
    op.execute("DELETE FROM protocols WHERE kind = 'exam'")
    op.drop_constraint("ck_protocols_kind", "protocols", type_="check")
    op.drop_column("protocols", "kind")
