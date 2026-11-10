"""Juego de emparejar expresiones como paso de un protocolo (bloque 5).

- protocol_steps admite kind = 'game' (game_type 'matching'): sin imagen propia,
  sin expresión pedida y sin captura automática; con rounds (2 a 6),
  option_count (2 a 4) y game_stimulus_ids, la imagen de cada ronda, que el
  servidor elige del banco aprobado al guardar el protocolo.
- guided_runs.game_progress: la ronda en curso y sus contadores (tamaño fijo).
- game_results: un registro por paso e intento, solo con contadores (rondas
  terminadas, emparejadas, a la primera, con ayuda y registradas por quien
  conduce). No es un puntaje.

Al volver atrás se borran los pasos de juego de los protocolos y sus
resultados. batch_alter_table permite correr la misma migración en SQLite.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_41"
down_revision = "20261106_40"
branch_labels = None
depends_on = None

OLD_KIND = "kind IN ('stimulus', 'practice', 'recognition', 'drawing')"
STEP_KIND = "kind IN ('stimulus', 'practice', 'recognition', 'drawing', 'game')"
OLD_STIMULUS = "kind IN ('practice', 'drawing') OR stimulus_id IS NOT NULL"
STEP_STIMULUS = "kind IN ('practice', 'drawing', 'game') OR stimulus_id IS NOT NULL"
_COMMON = (
    "((kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 "
    "AND option_count IS NULL) OR "
    "(kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0) OR "
    "(kind = 'drawing' AND stimulus_id IS NULL AND target_expression IS NULL AND hold_seconds IS NULL "
    "AND option_count IS NULL AND capture_after_seconds = 0)")
_TAIL = (
    " AND (situation IS NULL OR kind = 'recognition') "
    "AND (imitate = false OR (kind = 'practice' AND stimulus_id IS NOT NULL))")
OLD_PRACTICE = _COMMON + ")" + _TAIL
STEP_PRACTICE = (
    _COMMON + " OR "
    "(kind = 'game' AND stimulus_id IS NULL AND target_expression IS NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0 AND game_type = 'matching' "
    "AND rounds BETWEEN 2 AND 6 AND game_stimulus_ids IS NOT NULL))" + _TAIL
    + " AND (kind = 'game' OR (game_type IS NULL AND rounds IS NULL AND game_stimulus_ids IS NULL))")


def _step_constraints(kind: str, stimulus: str, practice: str) -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_kind", type_="check")
        batch.drop_constraint("ck_protocol_steps_stimulus", type_="check")
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_kind", kind)
        batch.create_check_constraint("ck_protocol_steps_stimulus", stimulus)
        batch.create_check_constraint("ck_protocol_steps_practice", practice)


def upgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("game_type", sa.String(16), nullable=True))
        batch.add_column(sa.Column("rounds", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("game_stimulus_ids", sa.JSON(), nullable=True))
    _step_constraints(STEP_KIND, STEP_STIMULUS, STEP_PRACTICE)
    with op.batch_alter_table("guided_runs") as batch:
        batch.add_column(sa.Column("game_progress", sa.JSON(), nullable=True))
    op.create_table(
        "game_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("game_type", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("rounds_total", sa.Integer(), nullable=False),
        sa.Column("rounds_done", sa.Integer(), nullable=False),
        sa.Column("matched", sa.Integer(), nullable=False),
        sa.Column("first_try", sa.Integer(), nullable=False),
        sa.Column("help_used", sa.Integer(), nullable=False),
        sa.Column("by_conductor", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "step_index", "attempt", name="uq_game_results_session_step_attempt"),
        sa.CheckConstraint("outcome IN ('completed', 'timed_out', 'skipped', 'stopped')",
                           name="ck_game_results_outcome"),
        sa.CheckConstraint("game_type = 'matching'", name="ck_game_results_type"),
        sa.CheckConstraint("first_try >= 0 AND first_try <= matched AND matched <= rounds_done "
                           "AND rounds_done <= rounds_total AND help_used >= 0 AND by_conductor >= 0",
                           name="ck_game_results_counts"),
    )
    op.create_index("ix_game_results_session_id", "game_results", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_game_results_session_id", table_name="game_results")
    op.drop_table("game_results")
    with op.batch_alter_table("guided_runs") as batch:
        batch.drop_column("game_progress")
    # Sin el tipo de paso, los juegos salen de los protocolos.
    op.execute(sa.text("DELETE FROM protocol_steps WHERE kind = 'game'"))
    _step_constraints(OLD_KIND, OLD_STIMULUS, OLD_PRACTICE)
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_column("game_stimulus_ids")
        batch.drop_column("rounds")
        batch.drop_column("game_type")
