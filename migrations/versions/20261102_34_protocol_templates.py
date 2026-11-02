"""Plantillas de protocolos.

- protocols.shared_with_group: el docente comparte un protocolo suyo con su
  grupo como plantilla; sus usuarios lo copian como protocolo propio, igual
  que los cuestionarios (questionnaires.shared_with_group). Los protocolos
  existentes quedan sin compartir.

Usa add_column y drop_column directos, como 20261102_33: protocols tiene
claves foráneas que impiden recrear la tabla en SQLite (pruebas).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_34"
down_revision = "20261102_33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("protocols", sa.Column("shared_with_group", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("protocols", "shared_with_group")
