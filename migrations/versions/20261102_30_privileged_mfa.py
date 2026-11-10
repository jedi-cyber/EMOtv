"""Segundo factor (TOTP) de las cuentas de gestión (superadmin y admin).

- mfa_secret: clave TOTP cifrada con SENSITIVE_DATA_KEY. Mientras mfa_enabled_at
  sea nulo es una clave en configuración que todavía no se confirmó.
- mfa_enabled_at: cuándo se confirmó la aplicación autenticadora.
- mfa_last_step: último intervalo de 30 s aceptado; un código no sirve dos veces.

Las cuentas existentes quedan sin segundo factor y lo configuran en su
siguiente ingreso.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261102_30"
down_revision = "20261030_29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("mfa_secret", sa.String(512), nullable=True))
        batch.add_column(sa.Column("mfa_enabled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("mfa_last_step", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("mfa_last_step")
        batch.drop_column("mfa_enabled_at")
        batch.drop_column("mfa_secret")
