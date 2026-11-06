"""Apoyos configurables por protocolo (docs/adaptacion-psicoeducacion.md, bloque 2b).

- support_pictograms, support_large_controls, support_read_aloud,
  support_no_time_limit y support_pause (normal, long o wait; lo valida el
  dominio con PauseMode).
- Un protocolo con el modo accesible de antes queda con el mismo preajuste:
  pictogramas, botones grandes y pausa larga. Se ve igual que antes.
- protocols.accessible se conserva e indica si el protocolo tiene algún apoyo.

Usa add_column y drop_column directos, como 20261102_33: protocols tiene
claves foráneas que impiden recrear la tabla en SQLite (pruebas).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_38"
down_revision = "20261106_37"
branch_labels = None
depends_on = None

FLAGS = ("support_pictograms", "support_large_controls", "support_read_aloud", "support_no_time_limit")


def upgrade() -> None:
    for name in FLAGS:
        op.add_column("protocols", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("protocols", sa.Column("support_pause", sa.String(8), nullable=False, server_default="normal"))
    op.execute(sa.text(
        "UPDATE protocols SET support_pictograms = :yes, support_large_controls = :yes, support_pause = 'long' "
        "WHERE accessible = :yes").bindparams(yes=True))


def downgrade() -> None:
    # accessible queda como estaba: verdadero si el protocolo tenía algún apoyo.
    op.drop_column("protocols", "support_pause")
    for name in reversed(FLAGS):
        op.drop_column("protocols", name)
