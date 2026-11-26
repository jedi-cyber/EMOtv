"""Paso «Usar el analizador» en los protocolos.

- protocol_steps: un paso de tipo 'analyzer' abre la lectura de la cámara sin
  imagen ni expresión pedida: quien conduce pide de palabra las expresiones y
  EMOtv registra la expresión estimada cada pocos segundos hasta que pulse
  «Siguiente paso» o venza su tiempo máximo, que puede llegar a 600 segundos
  (los demás pasos siguen hasta 120).

Al volver atrás, los pasos 'analyzer' se borran: no hay otro tipo de paso que
haga lo mismo sin inventar una imagen o una expresión. batch_alter_table
permite correr la misma migración en SQLite.
"""
from alembic import op

revision = "20261124_49"
down_revision = "20261124_48"
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
    " BETWEEN 2 AND 6 AND game_stimulus_ids IS NOT NULL){analyzer}) AND (situation IS NULL OR kind = 'recognition')"
    " AND (imitate = false OR (kind = 'practice' AND stimulus_id IS NOT NULL)) AND (kind = 'game' OR (gam"
    'e_type IS NULL AND rounds IS NULL AND game_stimulus_ids IS NULL))')
ANALYZER = (" OR (kind = 'analyzer' AND stimulus_id IS NULL AND target_expression IS NULL AND hold_seconds IS NULL"
            " AND option_count IS NULL AND capture_after_seconds = 0)")
KINDS = "kind IN ('stimulus', 'practice', 'recognition', 'drawing', 'game'{analyzer})"
STIMULUS = "kind IN ('practice', 'drawing', 'game'{analyzer}) OR stimulus_id IS NOT NULL"
NEW_EXPOSURE = "exposure_seconds BETWEEN 1 AND 600 AND (kind = 'analyzer' OR exposure_seconds <= 120)"
OLD_EXPOSURE = "exposure_seconds BETWEEN 1 AND 120"


def _constraints(analyzer: bool) -> None:
    kind = ", 'analyzer'" if analyzer else ""
    with op.batch_alter_table("protocol_steps") as batch:
        for name in ("exposure", "kind", "stimulus", "practice"):
            batch.drop_constraint(f"ck_protocol_steps_{name}", type_="check")
        batch.create_check_constraint("ck_protocol_steps_exposure", NEW_EXPOSURE if analyzer else OLD_EXPOSURE)
        batch.create_check_constraint("ck_protocol_steps_kind", KINDS.format(analyzer=kind))
        batch.create_check_constraint("ck_protocol_steps_stimulus", STIMULUS.format(analyzer=kind))
        batch.create_check_constraint("ck_protocol_steps_practice",
                                      _PRACTICE.format(analyzer=ANALYZER if analyzer else ""))


def upgrade() -> None:
    _constraints(True)


def downgrade() -> None:
    op.execute("DELETE FROM protocol_steps WHERE kind = 'analyzer'")
    _constraints(False)
