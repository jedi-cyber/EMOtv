"""Modelo local predeterminado elegido por el superadministrador y tipo de sesión.

local_model_settings guarda una sola fila: el modelo predeterminado, quién lo
cambió y cuándo, y la última vez que el sistema usó el respaldo. Sin fila rige
HSEmotion. Las sesiones existentes quedan como "propia" (quien inicia sesión se
analiza a sí mismo).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_17"
down_revision = "20261009_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "local_model_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("default_model_id", sa.String(128), nullable=False),
        sa.Column("changed_by_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fallback_model_id", sa.String(128), nullable=True),
        sa.Column("fallback_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_local_model_settings_single_row"),
        sa.CheckConstraint(
            "default_model_id IN ('hsemotion_enet_b0_8_best_afew', 'ferplus_onnx')",
            name="ck_local_model_settings_default_model",
        ),
        sa.CheckConstraint(
            "(fallback_model_id IS NULL AND fallback_at IS NULL) OR "
            "(fallback_model_id IS NOT NULL AND fallback_at IS NOT NULL)",
            name="ck_local_model_settings_fallback_fields",
        ),
    )
    op.add_column("sessions", sa.Column("session_type", sa.String(32), nullable=False,
                                        server_default="propia"))
    op.create_check_constraint(
        "ck_sessions_session_type", "sessions",
        "session_type IN ('propia', 'participante_adulto', 'participante_infantil')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_session_type", "sessions", type_="check")
    op.drop_column("sessions", "session_type")
    op.drop_table("local_model_settings")
