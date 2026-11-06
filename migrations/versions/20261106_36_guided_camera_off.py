"""Seguir sin cámara en guided_runs (docs/adaptacion-psicoeducacion.md, bloque 2).

- camera_off_at: momento en que quien conduce siguió sin cámara (permiso
  denegado, sin cámara o falla). Desde entonces no se calibra y los pasos que
  necesitan la cámara se saltan. Las sesiones existentes quedan con la cámara.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_36"
down_revision = "20261104_35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("guided_runs") as batch:
        batch.add_column(sa.Column("camera_off_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("guided_runs") as batch:
        batch.drop_column("camera_off_at")
