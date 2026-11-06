"""El dibujo como paso de un protocolo, con registro mínimo (bloque 4, subtarea 4a).

- protocol_steps admite kind = 'drawing': sin imagen, sin expresión pedida, sin
  tiempo de sostén, sin opciones y sin captura automática.
- drawing_results: la emoción que la persona señaló, los tiempos, cómo terminó
  el paso, quién registró la respuesta y el intento. Nunca el dibujo: no llega
  al servidor.

Al volver atrás se borran los pasos de dibujo de los protocolos y sus
resultados. Se usa batch_alter_table para que la misma migración corra en
SQLite (pruebas); en PostgreSQL emite ALTER TABLE directos.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_40"
down_revision = "20261106_39"
branch_labels = None
depends_on = None

OLD_KIND = "kind IN ('stimulus', 'practice', 'recognition')"
STEP_KIND = "kind IN ('stimulus', 'practice', 'recognition', 'drawing')"
OLD_STIMULUS = "kind = 'practice' OR stimulus_id IS NOT NULL"
STEP_STIMULUS = "kind IN ('practice', 'drawing') OR stimulus_id IS NOT NULL"
OLD_PRACTICE = (
    "((kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 "
    "AND option_count IS NULL) OR "
    "(kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0)) "
    "AND (situation IS NULL OR kind = 'recognition') "
    "AND (imitate = false OR (kind = 'practice' AND stimulus_id IS NOT NULL))")
STEP_PRACTICE = (
    "((kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 "
    "AND option_count IS NULL) OR "
    "(kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0) OR "
    "(kind = 'drawing' AND stimulus_id IS NULL AND target_expression IS NULL AND hold_seconds IS NULL "
    "AND option_count IS NULL AND capture_after_seconds = 0)) "
    "AND (situation IS NULL OR kind = 'recognition') "
    "AND (imitate = false OR (kind = 'practice' AND stimulus_id IS NOT NULL))")


def _step_constraints(kind: str, stimulus: str, practice: str) -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_kind", type_="check")
        batch.drop_constraint("ck_protocol_steps_stimulus", type_="check")
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_kind", kind)
        batch.create_check_constraint("ck_protocol_steps_stimulus", stimulus)
        batch.create_check_constraint("ck_protocol_steps_practice", practice)


def upgrade() -> None:
    _step_constraints(STEP_KIND, STEP_STIMULUS, STEP_PRACTICE)
    op.create_table(
        "drawing_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("chosen_expression", sa.String(32), nullable=True),
        sa.Column("seconds_to_answer", sa.Float(), nullable=True),
        sa.Column("answered_by", sa.String(16), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "step_index", "attempt", name="uq_drawing_results_session_step_attempt"),
        sa.CheckConstraint("outcome IN ('answered', 'timed_out', 'skipped', 'stopped')",
                           name="ck_drawing_results_outcome"),
        sa.CheckConstraint("(outcome = 'answered') = (chosen_expression IS NOT NULL) "
                           "AND (outcome = 'answered') = (seconds_to_answer IS NOT NULL) "
                           "AND (outcome = 'answered') = (answered_by IS NOT NULL)",
                           name="ck_drawing_results_answered"),
        sa.CheckConstraint("answered_by IS NULL OR answered_by IN ('participant', 'conductor')",
                           name="ck_drawing_results_answered_by"),
    )
    op.create_index("ix_drawing_results_session_id", "drawing_results", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_drawing_results_session_id", table_name="drawing_results")
    op.drop_table("drawing_results")
    # Sin el tipo de paso, los dibujos salen de los protocolos.
    op.execute(sa.text("DELETE FROM protocol_steps WHERE kind = 'drawing'"))
    _step_constraints(OLD_KIND, OLD_STIMULUS, OLD_PRACTICE)
