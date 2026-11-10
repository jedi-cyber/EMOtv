"""Situaciones en el paso «¿Qué emoción es?».

- protocol_steps.situation: historia corta opcional de un reconocimiento
  («A Lucía se le cayó su helado»). Con ella la pregunta es «¿Cómo se siente?».
  Solo la llevan los pasos de reconocimiento: la regla se agrega a
  ck_protocol_steps_practice, que las migraciones anteriores ya saben quitar.

Se usa batch_alter_table para que la misma migración corra en SQLite (pruebas);
en PostgreSQL emite ALTER TABLE directos.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_32"
down_revision = "20261102_31"
branch_labels = None
depends_on = None

OLD_PRACTICE = (
    "(kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL) OR "
    "(kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL "
    "AND hold_seconds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 "
    "AND option_count IS NULL) OR "
    "(kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL "
    "AND option_count BETWEEN 2 AND 4 AND capture_after_seconds = 0)")
STEP_PRACTICE = f"({OLD_PRACTICE}) AND (situation IS NULL OR kind = 'recognition')"


def upgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("situation", sa.String(200), nullable=True))
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_practice", STEP_PRACTICE)


def downgrade() -> None:
    # Los reconocimientos con situación quedan como reconocimientos de la imagen.
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_practice", OLD_PRACTICE)
        batch.drop_column("situation")
