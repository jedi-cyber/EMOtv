"""Pantalla de la persona en Android (bloque 8).

guided_runs agrega:

- pairing_hash: SHA-256 del código de un solo uso que quien conduce pide
  en la web para vincular Android (nunca el código en claro);
- pairing_expires_at: cuándo vence ese código;
- view_device: 'web' o 'android', dónde está abierta la pantalla de la persona.
  Las sesiones existentes quedan en 'web'.

Al volver atrás se borran las columnas: los códigos pendientes dejan de valer y
las pantallas Android abiertas siguen con su enlace hasta que termine la sesión.
batch_alter_table permite correr la misma migración en SQLite.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261107_43"
down_revision = "20261107_42"


def upgrade() -> None:
    with op.batch_alter_table("guided_runs") as batch:
        batch.add_column(sa.Column("pairing_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("pairing_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("view_device", sa.String(8), nullable=False, server_default="web"))
        batch.create_unique_constraint("uq_guided_runs_pairing_hash", ["pairing_hash"])
        batch.create_check_constraint("ck_guided_runs_view_device", "view_device IN ('web', 'android')")
        batch.create_check_constraint("ck_guided_runs_pairing",
                                      "(pairing_hash IS NULL) = (pairing_expires_at IS NULL)")


def downgrade() -> None:
    with op.batch_alter_table("guided_runs") as batch:
        batch.drop_constraint("ck_guided_runs_pairing", type_="check")
        batch.drop_constraint("ck_guided_runs_view_device", type_="check")
        batch.drop_constraint("uq_guided_runs_pairing_hash", type_="unique")
        batch.drop_column("view_device")
        batch.drop_column("pairing_expires_at")
        batch.drop_column("pairing_hash")
