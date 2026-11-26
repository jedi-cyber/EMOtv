"""Eliminar protocolos y cuestionarios.

- protocols.deleted_at y questionnaires.deleted_at: quien los armó los elimina.
  Dejan de listarse, de aplicarse y de ofrecerse como plantilla; las sesiones
  que los usaron los conservan para su línea de tiempo, sus respuestas y su
  reporte. Se usa batch_alter_table para correr también en SQLite (pruebas).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261124_47"
down_revision = "20261124_46"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("protocols", "questionnaires"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Lo eliminado vuelve a listarse: la versión anterior no sabe ocultarlo.
    for table in ("questionnaires", "protocols"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("deleted_at")
