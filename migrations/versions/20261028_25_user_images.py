"""Imágenes propias de los usuarios con detección de personas y revisión del docente.

- stimuli: alcance 'user' (imagen que sube un usuario para sus protocolos;
  queda pendiente hasta que su docente la revisa). Una imagen propia no indica
  expresión esperada. Columnas possible_person (la detección automática dudó),
  upload_batch_id (lote de subida), expiry_notified_at (aviso de vencimiento)
  y deleted_at (eliminada: sin archivo, se conserva solo si una sesión o un
  protocolo la nombran).
- user_notices: avisos para una cuenta (imagen eliminada con su motivo,
  vencimiento próximo, protocolo que necesita una imagen).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261028_25"
down_revision = "20261027_24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_stimuli_scope", "stimuli", type_="check")
    op.create_check_constraint("ck_stimuli_scope", "stimuli", "scope IN ('group', 'institution', 'user')")
    op.drop_constraint("ck_stimuli_expected_expression", "stimuli", type_="check")
    op.create_check_constraint(
        "ck_stimuli_expected_expression", "stimuli",
        "(kind = 'emotional' AND (expected_expression IS NOT NULL OR scope = 'user')) OR "
        "(kind = 'abstract' AND expected_expression IS NULL)")
    op.add_column("stimuli", sa.Column("possible_person", sa.Boolean(), nullable=False,
                                       server_default=sa.text("false")))
    op.add_column("stimuli", sa.Column("upload_batch_id", sa.String(36), nullable=True))
    op.add_column("stimuli", sa.Column("expiry_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stimuli", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_stimuli_upload_batch_id", "stimuli", ["upload_batch_id"])
    op.create_table(
        "user_notices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message", sa.String(800), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_notices_user_id", "user_notices", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_notices_user_id", table_name="user_notices")
    op.drop_table("user_notices")
    op.execute("DELETE FROM stimuli WHERE scope = 'user'")
    op.drop_index("ix_stimuli_upload_batch_id", table_name="stimuli")
    for column in ("deleted_at", "expiry_notified_at", "upload_batch_id", "possible_person"):
        op.drop_column("stimuli", column)
    op.drop_constraint("ck_stimuli_expected_expression", "stimuli", type_="check")
    op.create_check_constraint(
        "ck_stimuli_expected_expression", "stimuli",
        "(kind = 'emotional' AND expected_expression IS NOT NULL) OR "
        "(kind = 'abstract' AND expected_expression IS NULL)")
    op.drop_constraint("ck_stimuli_scope", "stimuli", type_="check")
    op.create_check_constraint("ck_stimuli_scope", "stimuli", "scope IN ('group', 'institution')")
