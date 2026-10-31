"""Práctica de producción de expresiones (docs/expression-practice.md).

- protocol_steps.kind: 'stimulus' (todos los pasos existentes) o 'practice'.
- protocol_steps.target_expression y hold_seconds: solo en una práctica.
- protocol_steps.stimulus_id admite nulo: la ilustración de una práctica es
  opcional; un paso de estímulo sigue exigiéndolo.
- practice_results: un resultado por paso de práctica y sesión. Sin imágenes,
  niveles por cuadro ni base neutral.

Se usa batch_alter_table para que la misma migración corra en SQLite (pruebas);
en PostgreSQL emite ALTER TABLE directos.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261030_28"
down_revision = "20261030_27"
branch_labels = None
depends_on = None

STEP_KIND = "kind IN ('stimulus', 'practice')"
STEP_STIMULUS = "kind = 'practice' OR stimulus_id IS NOT NULL"
STEP_PRACTICE = (
    "(kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0)")


def upgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("kind", sa.String(16), nullable=False, server_default=sa.text("'stimulus'")))
        batch.add_column(sa.Column("target_expression", sa.String(32), nullable=True))
        batch.add_column(sa.Column("hold_seconds", sa.Integer(), nullable=True))
        batch.alter_column("stimulus_id", existing_type=sa.String(36), nullable=True)
        batch.create_check_constraint("ck_protocol_steps_kind", STEP_KIND)
        batch.create_check_constraint("ck_protocol_steps_stimulus", STEP_STIMULUS)
        batch.create_check_constraint("ck_protocol_steps_practice", STEP_PRACTICE)

    op.create_table(
        "practice_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("target_expression", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("seconds_to_achieve", sa.Float(), nullable=True),
        sa.Column("peak_level", sa.Float(), nullable=False),
        sa.Column("relative_to_calibration", sa.Boolean(), nullable=False),
        sa.Column("feedback_visible", sa.Boolean(), nullable=False),
        sa.Column("analyzed_frames", sa.Integer(), nullable=False),
        sa.Column("flagged_frames", sa.Integer(), nullable=False),
        sa.Column("emotion_model_id", sa.String(128), nullable=False),
        sa.Column("emotion_model_version", sa.String(128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "step_index", name="uq_practice_results_session_step"),
        sa.CheckConstraint("outcome IN ('achieved', 'timed_out', 'skipped', 'stopped')",
                           name="ck_practice_results_outcome"),
        sa.CheckConstraint("(outcome = 'achieved') = (seconds_to_achieve IS NOT NULL)",
                           name="ck_practice_results_achieved"),
        sa.CheckConstraint("peak_level >= 0 AND peak_level <= 1", name="ck_practice_results_peak"),
    )
    op.create_index("ix_practice_results_session_id", "practice_results", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_practice_results_session_id", table_name="practice_results")
    op.drop_table("practice_results")
    # La versión anterior no conoce las prácticas: sus pasos se quitan de los
    # protocolos. Los pasos de estímulo quedan igual.
    op.execute("DELETE FROM protocol_steps WHERE kind = 'practice'")
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.drop_constraint("ck_protocol_steps_stimulus", type_="check")
        batch.drop_constraint("ck_protocol_steps_kind", type_="check")
        batch.alter_column("stimulus_id", existing_type=sa.String(36), nullable=False)
        batch.drop_column("hold_seconds")
        batch.drop_column("target_expression")
        batch.drop_column("kind")
