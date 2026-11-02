"""Paso de reconocimiento de emociones: «¿Qué emoción es?».

- protocol_steps.kind admite 'recognition': una imagen emocional del banco,
  su expresión esperada como respuesta correcta y option_count opciones.
- recognition_results: uno por paso de reconocimiento y sesión. Guarda las
  opciones mostradas y la elegida; nunca imágenes ni datos de la cámara.

Se usa batch_alter_table para que la misma migración corra en SQLite (pruebas);
en PostgreSQL emite ALTER TABLE directos.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_31"
down_revision = "20261102_30"
branch_labels = None
depends_on = None

OLD_KIND = "kind IN ('stimulus', 'practice')"
OLD_STIMULUS = "kind = 'practice' OR stimulus_id IS NOT NULL"
OLD_PRACTICE = (
    "(kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0)")

STEP_KIND = "kind IN ('stimulus', 'practice', 'recognition')"
STEP_STIMULUS = "kind = 'practice' OR stimulus_id IS NOT NULL"
STEP_PRACTICE = (
    "(kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 "
    "AND option_count IS NULL) OR "
    "(kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0)")


def upgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("option_count", sa.Integer(), nullable=True))
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.drop_constraint("ck_protocol_steps_kind", type_="check")
        batch.create_check_constraint("ck_protocol_steps_kind", STEP_KIND)
        batch.create_check_constraint("ck_protocol_steps_practice", STEP_PRACTICE)

    op.create_table(
        "recognition_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("stimulus_id", sa.String(36), nullable=False),
        sa.Column("target_expression", sa.String(32), nullable=False),
        sa.Column("options", sa.String(160), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("chosen_expression", sa.String(32), nullable=True),
        sa.Column("seconds_to_answer", sa.Float(), nullable=True),
        sa.Column("answered_by", sa.String(16), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "step_index", name="uq_recognition_results_session_step"),
        sa.CheckConstraint("outcome IN ('answered', 'timed_out', 'skipped', 'stopped')",
                           name="ck_recognition_results_outcome"),
        sa.CheckConstraint("(outcome = 'answered') = (chosen_expression IS NOT NULL) "
                           "AND (outcome = 'answered') = (seconds_to_answer IS NOT NULL) "
                           "AND (outcome = 'answered') = (answered_by IS NOT NULL)",
                           name="ck_recognition_results_answered"),
        sa.CheckConstraint("answered_by IS NULL OR answered_by IN ('participant', 'conductor')",
                           name="ck_recognition_results_answered_by"),
    )
    op.create_index("ix_recognition_results_session_id", "recognition_results", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_recognition_results_session_id", table_name="recognition_results")
    op.drop_table("recognition_results")
    # La versión anterior no conoce los reconocimientos: sus pasos se quitan.
    op.execute("DELETE FROM protocol_steps WHERE kind = 'recognition'")
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.drop_constraint("ck_protocol_steps_kind", type_="check")
        batch.create_check_constraint("ck_protocol_steps_kind", OLD_KIND)
        batch.create_check_constraint("ck_protocol_steps_practice", OLD_PRACTICE)
        batch.drop_column("option_count")
