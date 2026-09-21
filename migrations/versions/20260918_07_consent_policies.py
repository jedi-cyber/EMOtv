"""Versioned consent policies with one active policy."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_07"
down_revision = "20260918_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("consent_policies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("code", sa.String(48), nullable=False),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.String(16000), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("code", "version", name="uq_consent_policies_code_version"))
    op.create_index("uq_consent_policies_single_active", "consent_policies", ["is_active"],
                    unique=True, postgresql_where=sa.text("is_active = true"),
                    sqlite_where=sa.text("is_active = 1"))


def downgrade() -> None:
    op.drop_index("uq_consent_policies_single_active", table_name="consent_policies")
    op.drop_table("consent_policies")
