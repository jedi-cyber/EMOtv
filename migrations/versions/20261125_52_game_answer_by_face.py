"""«Responde con la cara» en los juegos.

- protocol_steps.answer_by_face: un juego que la persona responde poniendo la cara
  de la emoción; la cámara marca la opción que coincide. Lo valida el dominio (solo
  en juegos y no junto con show_expression). No se guarda ninguna imagen: los
  resultados siguen siendo los contadores del juego.

Al volver atrás se quita la columna y los juegos se responden con botones.
batch_alter_table permite correr la misma migración en SQLite.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261125_52"
down_revision = "20261124_51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("answer_by_face", sa.Boolean(), nullable=False,
                                   server_default=sa.text("false")))


def downgrade() -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_column("answer_by_face")
