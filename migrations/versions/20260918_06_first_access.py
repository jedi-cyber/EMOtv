"""Track accounts that must replace their provisional password."""
from alembic import op
import sqlalchemy as sa

revision = "20260918_06"
down_revision = "20260916_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(),
                                     nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("token_version", sa.Integer(),
                                     nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "token_version")
    op.drop_column("users", "must_change_password")
