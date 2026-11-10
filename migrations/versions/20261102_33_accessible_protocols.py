"""Modo accesible de un protocolo.

- protocols.accessible: la pantalla de la persona muestra pictogramas junto a
  cada emoción, botones y letra más grandes, sin animaciones, y la pausa tras
  cada ejercicio o reconocimiento es más larga. Los protocolos existentes
  quedan sin modo accesible.

Usa add_column y drop_column directos, como 20261029_26: protocols tiene
claves foráneas que impiden recrear la tabla en SQLite (pruebas).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_33"
down_revision = "20261102_32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("protocols", sa.Column("accessible", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("protocols", "accessible")
