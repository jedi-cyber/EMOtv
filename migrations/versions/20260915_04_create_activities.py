"""Persist activities and seed the initial catalog."""
from alembic import op
import sqlalchemy as sa

revision = "20260915_04"
down_revision = "20260908_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table("activities",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("required_posture", sa.String(32), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.CheckConstraint("duration_seconds > 0", name="ck_activities_duration_positive"),
        sa.CheckConstraint("repetitions >= 1", name="ck_activities_repetitions_positive"),
        sa.CheckConstraint("required_posture IN ('arms_up','arms_open','arms_forward','hands_on_hips','squat')", name="ck_activities_posture_valid"))
    op.bulk_insert(table, [
        dict(id="arms_up_5s", name="Elevación de brazos", description="Levanta ambos brazos y mantenlos extendidos sobre los hombros.", required_posture="arms_up", duration_seconds=5.0, repetitions=1),
        dict(id="arms_open_5s", name="Apertura de brazos", description="Abre ambos brazos a la altura de los hombros.", required_posture="arms_open", duration_seconds=5.0, repetitions=1),
        dict(id="hands_on_hips_5s", name="Manos en las caderas", description="Coloca las manos en las caderas y mantén los codos abiertos.", required_posture="hands_on_hips", duration_seconds=5.0, repetitions=1),
    ])


def downgrade() -> None:
    op.drop_table("activities")
