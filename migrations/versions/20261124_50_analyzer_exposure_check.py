"""ck_protocol_steps_exposure vuelve a mirar solo su columna.

20261124_49 puso en ck_protocol_steps_exposure el tope de 120 s de los pasos que
no son «Usar el analizador», y eso hacía depender la restricción de la columna
kind. Ahora el tope va en ck_protocol_steps_practice, que ya depende de kind, y
ck_protocol_steps_exposure solo exige de 1 a 600 s. Lo que se acepta no cambia.
batch_alter_table permite correr la misma migración en SQLite.
"""

from alembic import op

revision = "20261124_50"
down_revision = "20261124_49"
branch_labels = None
depends_on = None

_PRACTICE = (
    "((kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL)"
    " OR (kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL AND hold_secon"
    'ds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 AND option_count IS NULL) '
    "OR (kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL AND option_count"
    " BETWEEN 2 AND 4 AND capture_after_seconds = 0) OR (kind = 'drawing' AND target_expression "
    'IS NULL AND hold_seconds IS NULL AND option_count IS NULL AND capture_after_seconds = 0) OR (kind = '
    "'game' AND stimulus_id IS NULL AND target_expression IS NULL AND hold_seconds IS NULL AND option_cou"
    "nt BETWEEN 2 AND 4 AND capture_after_seconds = 0 AND game_type IN ('matching', 'similar') AND rounds"
    " BETWEEN 2 AND 6 AND game_stimulus_ids IS NOT NULL) OR (kind = 'analyzer' AND stimulus_id IS NULL"
    " AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL AND capture_after_seconds = 0))"
    " AND (situation IS NULL OR kind = 'recognition'){limit}"
    " AND (imitate = false OR (kind = 'practice' AND stimulus_id IS NOT NULL)) AND (kind = 'game' OR (gam"
    'e_type IS NULL AND rounds IS NULL AND game_stimulus_ids IS NULL))')
LIMIT = " AND (kind = 'analyzer' OR exposure_seconds <= 120)"
NEW_EXPOSURE = "exposure_seconds BETWEEN 1 AND 600"
OLD_EXPOSURE = "exposure_seconds BETWEEN 1 AND 600 AND (kind = 'analyzer' OR exposure_seconds <= 120)"


def _constraints(exposure: str, limit: str) -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_exposure", type_="check")
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_exposure", exposure)
        batch.create_check_constraint("ck_protocol_steps_practice", _PRACTICE.format(limit=limit))


def upgrade() -> None:
    _constraints(NEW_EXPOSURE, LIMIT)


def downgrade() -> None:
    _constraints(OLD_EXPOSURE, "")
