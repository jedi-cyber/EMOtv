"""Sesiones del aplicativo móvil.

- mobile_sessions: token de renovación revocable (solo su SHA-256), el anterior
  para detectar reutilización, versión de la contraseña al emitirlo y fechas.
  Sin datos del dispositivo ni IP.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261026_23"
down_revision = "20261025_22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mobile_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("previous_token_hash", sa.String(64), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("refresh_token_hash", name="uq_mobile_sessions_refresh_token_hash"),
    )
    op.create_index("ix_mobile_sessions_user_id", "mobile_sessions", ["user_id"])
    op.create_index("ix_mobile_sessions_previous_token_hash", "mobile_sessions", ["previous_token_hash"])
    op.create_index("ix_mobile_sessions_expires_at", "mobile_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_mobile_sessions_expires_at", table_name="mobile_sessions")
    op.drop_index("ix_mobile_sessions_previous_token_hash", table_name="mobile_sessions")
    op.drop_index("ix_mobile_sessions_user_id", table_name="mobile_sessions")
    op.drop_table("mobile_sessions")
