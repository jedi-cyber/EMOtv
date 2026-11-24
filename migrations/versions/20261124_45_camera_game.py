"""Juego con cámara («Muestra la emoción»).

- protocol_steps.game_round: la ronda (1 a 6) de un juego con cámara. Cada ronda
  es una práctica sin imagen que pide una de las cinco expresiones que estima
  EMOtv; el bloque de rondas seguidas lo valida el dominio. La regla de la
  columna va en una restricción propia, sin tocar ck_protocol_steps_practice.

Se usa batch_alter_table para que la misma migración corra en SQLite (pruebas);
en PostgreSQL emite ALTER TABLE directos.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261124_45"
down_revision = "20261123_44"
branch_labels = None
depends_on = None

# Solo la propia columna: las migraciones anteriores, al deshacerse, quitan
# columnas como imitate o kind y no conocen esta restricción. Que la ronda sea
# una práctica sin imagen lo valida el dominio.
GAME_ROUND = "game_round IS NULL OR game_round BETWEEN 1 AND 6"


def upgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("game_round", sa.Integer(), nullable=True))
        batch.create_check_constraint("ck_protocol_steps_game_round", GAME_ROUND)


def downgrade() -> None:
    # Las rondas quedan como ejercicios de práctica sueltos.
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_game_round", type_="check")
        batch.drop_column("game_round")
