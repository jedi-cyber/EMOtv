"""«Reconoce y luego muéstrala» en los juegos.

- protocol_steps.show_expression: un juego que, al terminar cada ronda, pide a la
  persona poner la cara de la emoción de la ronda mientras la cámara estima la
  expresión. Lo valida el dominio (solo en juegos).
- game_results.faces_asked y faces_shown: en cuántas rondas se pidió la cara y en
  cuántas la cámara estimó que la sostuvo. Nulos en los juegos que no lo piden.
  La restricción solo mira columnas de la propia tabla.

Al volver atrás se quitan las columnas: los juegos quedan sin esa parte y sus
resultados conservan los demás contadores. batch_alter_table permite correr la
misma migración en SQLite.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261124_51"
down_revision = "20261124_50"
branch_labels = None
depends_on = None

FACES = ("(faces_asked IS NULL AND faces_shown IS NULL) OR "
         "(faces_shown >= 0 AND faces_shown <= faces_asked AND faces_asked <= rounds_done)")


def upgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("show_expression", sa.Boolean(), nullable=False,
                                   server_default=sa.text("false")))
    with op.batch_alter_table("game_results") as batch:
        batch.add_column(sa.Column("faces_asked", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("faces_shown", sa.Integer(), nullable=True))
        batch.create_check_constraint("ck_game_results_faces", FACES)


def downgrade() -> None:
    with op.batch_alter_table("game_results") as batch:
        batch.drop_constraint("ck_game_results_faces", type_="check")
        batch.drop_column("faces_shown")
        batch.drop_column("faces_asked")
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_column("show_expression")
