"""Registro de intentos de inicio de sesión para limitar fallos."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_09"
down_revision = "20260921_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("ip", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"])
    op.create_index("ix_login_attempts_ip_created_at", "login_attempts", ["ip", "created_at"])
    op.create_index("ix_login_attempts_account_created_at", "login_attempts",
                    ["email_hash", "ip", "created_at"])


def downgrade() -> None:
    op.drop_table("login_attempts")
