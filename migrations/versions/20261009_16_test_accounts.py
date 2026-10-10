"""Indicador de cuenta de prueba (voluntarios PRUEBA-NN).

Solo las cuentas con users.is_test_account verdadero pueden eliminarse con
scripts/testdata/delete_test_data.py. Las cuentas existentes quedan en falso.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_16"
down_revision = "20261009_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_test_account", sa.Boolean(), nullable=False,
                                     server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_test_account")
