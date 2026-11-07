"""Juego «Busca la misma emoción» (bloque 6).

- protocol_steps admite game_type 'similar', además de 'matching'. Sus
  game_stimulus_ids guardan, por ronda, la imagen modelo, la otra de la misma
  emoción y una de otra emoción por cada opción restante.
- game_results admite game_type 'similar'. Los contadores son los mismos.

Al volver atrás se borran los pasos 'similar' de los protocolos y sus
resultados. batch_alter_table permite correr la misma migración en SQLite.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261107_42"
down_revision = "20261106_41"

_COMMON = (
    "((kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 "
    "AND option_count IS NULL) OR "
    "(kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0) OR "
    "(kind = 'drawing' AND stimulus_id IS NULL AND target_expression IS NULL AND hold_seconds IS NULL "
    "AND option_count IS NULL AND capture_after_seconds = 0) OR "
    "(kind = 'game' AND stimulus_id IS NULL AND target_expression IS NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0 AND {types} "
    "AND rounds BETWEEN 2 AND 6 AND game_stimulus_ids IS NOT NULL)) "
    "AND (situation IS NULL OR kind = 'recognition') "
    "AND (imitate = false OR (kind = 'practice' AND stimulus_id IS NOT NULL)) "
    "AND (kind = 'game' OR (game_type IS NULL AND rounds IS NULL AND game_stimulus_ids IS NULL))")
OLD_TYPES = "game_type = 'matching'"
TYPES = "game_type IN ('matching', 'similar')"


def _constraints(types: str) -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_practice", _COMMON.format(types=types))
    with op.batch_alter_table("game_results") as batch:
        batch.drop_constraint("ck_game_results_type", type_="check")
        batch.create_check_constraint("ck_game_results_type", types)


def upgrade() -> None:
    _constraints(TYPES)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM game_results WHERE game_type = 'similar'"))
    op.execute(sa.text("DELETE FROM protocol_steps WHERE kind = 'game' AND game_type = 'similar'"))
    _constraints(OLD_TYPES)
