"""Imitar un modelo en los ejercicios de práctica.

- protocol_steps.imitate: la práctica muestra su ilustración como modelo y la
  persona lee «Haz la misma cara». La expresión pedida es la esperada de la
  imagen. Solo una práctica con imagen puede imitar: la regla se agrega a
  ck_protocol_steps_practice.

Se usa batch_alter_table para que la misma migración corra en SQLite (pruebas);
en PostgreSQL emite ALTER TABLE directos.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_35"
down_revision = "20261102_34"
branch_labels = None
depends_on = None

OLD_PRACTICE = (
    "((kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 "
    "AND option_count IS NULL) OR "
    "(kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0)) "
    "AND (situation IS NULL OR kind = 'recognition')")
STEP_PRACTICE = (f"{OLD_PRACTICE} "
                 "AND (imitate = false OR (kind = 'practice' AND stimulus_id IS NOT NULL))")


def upgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("imitate", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_practice", STEP_PRACTICE)


def downgrade() -> None:
    # Las imitaciones quedan como prácticas con ilustración.
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_practice", OLD_PRACTICE)
        batch.drop_column("imitate")
