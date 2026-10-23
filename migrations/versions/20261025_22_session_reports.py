"""Reportes de sesión con revisión del docente.

- session_reports: versiones del reporte; el texto se cifra con SENSITIVE_DATA_KEY.
- report_comments: comentarios del docente por sección, cifrados.
- report_events: historial sin contenido (quién hizo qué y cuándo).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261025_22"
down_revision = "20261024_21"
branch_labels = None
depends_on = None


def _participant():
    return sa.Column("participant_id", sa.String(36), sa.ForeignKey("participants.id", ondelete="CASCADE"),
                     nullable=False)


def _report():
    return sa.Column("report_id", sa.String(36), sa.ForeignKey("session_reports.id", ondelete="CASCADE"),
                     nullable=False)


def upgrade() -> None:
    op.create_table(
        "session_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        _participant(),
        sa.Column("author_user_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("narrative_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(64), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("family_id", "version", name="uq_session_reports_family_version"),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'changes_requested', 'approved')",
                           name="ck_session_reports_status"),
        sa.CheckConstraint("(status = 'approved') = (approved_at IS NOT NULL)", name="ck_session_reports_approval"),
    )
    for column in ("family_id", "session_id", "participant_id", "author_user_id"):
        op.create_index(f"ix_session_reports_{column}", "session_reports", [column])

    op.create_table(
        "report_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        _report(),
        _participant(),
        sa.Column("section", sa.String(24), nullable=False),
        sa.Column("text_encrypted", sa.Text(), nullable=False),
        sa.Column("author_user_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("section IN ('timeline', 'metrics', 'questionnaires', 'narrative', 'general')",
                           name="ck_report_comments_section"),
    )
    op.create_table(
        "report_events",
        sa.Column("id", sa.String(36), primary_key=True),
        _report(),
        _participant(),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('created', 'edited', 'submitted', 'commented', 'returned', 'approved', "
                           "'closed', 'new_version', 'printed')", name="ck_report_events_action"),
    )
    for table in ("report_comments", "report_events"):
        op.create_index(f"ix_{table}_report_id", table, ["report_id"])
        op.create_index(f"ix_{table}_participant_id", table, ["participant_id"])


def downgrade() -> None:
    op.drop_table("report_events")
    op.drop_table("report_comments")
    op.drop_table("session_reports")
