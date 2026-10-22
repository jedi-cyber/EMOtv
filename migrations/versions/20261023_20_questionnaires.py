"""Cuestionarios creados por quien conduce la sesión y sus respuestas cifradas.

- questionnaires: versiones de cada cuestionario (preguntas en JSON).
- questionnaire_responses: respuestas cifradas con SENSITIVE_DATA_KEY, por
  sesión y momento (previo o posterior), con la versión exacta respondida.
- sessions.pre_questionnaire_id y sessions.post_questionnaire_id.
- protocols.post_questionnaire_id y la clave foránea de pre_questionnaire_id
  (hasta ahora siempre nulo).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261023_20"
down_revision = "20261022_19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "questionnaires",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("instructions", sa.String(2000), nullable=False, server_default=""),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("shared_with_group", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("copied_from_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("family_id", "version", name="uq_questionnaires_family_version"),
        sa.CheckConstraint("version >= 1", name="ck_questionnaires_version"),
    )
    op.create_index("ix_questionnaires_family_id", "questionnaires", ["family_id"])
    op.create_index("ix_questionnaires_owner_user_id", "questionnaires", ["owner_user_id"])

    op.create_table(
        "questionnaire_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("questionnaire_id", sa.String(36), sa.ForeignKey("questionnaires.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("participant_id", sa.String(36), sa.ForeignKey("participants.id", ondelete="CASCADE"),
                  nullable=True),
        sa.Column("moment", sa.String(8), nullable=False),
        sa.Column("answers_encrypted", sa.Text(), nullable=False),
        sa.Column("entry_mode", sa.String(16), nullable=False),
        sa.Column("recorded_by_user_id", sa.String(64), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "moment", name="uq_questionnaire_responses_session_moment"),
        sa.CheckConstraint("moment IN ('pre', 'post')", name="ck_questionnaire_responses_moment"),
        sa.CheckConstraint("entry_mode IN ('participant', 'conductor')",
                           name="ck_questionnaire_responses_entry_mode"),
    )
    for column in ("session_id", "questionnaire_id", "participant_id"):
        op.create_index(f"ix_questionnaire_responses_{column}", "questionnaire_responses", [column])

    for column in ("pre_questionnaire_id", "post_questionnaire_id"):
        op.add_column("sessions", sa.Column(column, sa.String(36), nullable=True))
        op.create_foreign_key(f"fk_sessions_{column}", "sessions", "questionnaires", [column], ["id"],
                              ondelete="RESTRICT")
        op.create_index(f"ix_sessions_{column}", "sessions", [column])

    op.add_column("protocols", sa.Column("post_questionnaire_id", sa.String(36), nullable=True))
    for column in ("pre_questionnaire_id", "post_questionnaire_id"):
        op.create_foreign_key(f"fk_protocols_{column}", "protocols", "questionnaires", [column], ["id"],
                              ondelete="RESTRICT")


def downgrade() -> None:
    for column in ("post_questionnaire_id", "pre_questionnaire_id"):
        op.drop_constraint(f"fk_protocols_{column}", "protocols", type_="foreignkey")
    op.drop_column("protocols", "post_questionnaire_id")
    for column in ("post_questionnaire_id", "pre_questionnaire_id"):
        op.drop_index(f"ix_sessions_{column}", "sessions")
        op.drop_constraint(f"fk_sessions_{column}", "sessions", type_="foreignkey")
        op.drop_column("sessions", column)
    op.drop_table("questionnaire_responses")
    op.drop_table("questionnaires")
