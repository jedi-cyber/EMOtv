"""Señal de la práctica en guided_runs (docs/expression-practice.md).

- practice_feedback: la persona ve el nivel durante los ejercicios de práctica.
  Quien conduce puede apagarla para toda la sesión. Las sesiones existentes
  quedan con la señal encendida.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261030_29"
down_revision = "20261030_28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("guided_runs") as batch:
        batch.add_column(sa.Column("practice_feedback", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("guided_runs") as batch:
        batch.drop_column("practice_feedback")
