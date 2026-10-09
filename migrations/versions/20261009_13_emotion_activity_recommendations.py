"""Asociaciones expresión -> actividad recomendada, editables por administración.

La semilla copia las asociaciones que estaban en código
(DEFAULT_ACTIVITIES_BY_EMOTION). Es una instantánea: las migraciones no deben
importar código de la aplicación. Solo se insertan pares cuya actividad existe,
para no fallar en bases donde administración eliminó alguna.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_13"
down_revision = "20261008_12"
branch_labels = None
depends_on = None

SEED = {
    "sadness": ("morning_mobility", "open_and_reach"),
    "anger": ("upper_body_flow", "balanced_postures"),
    "neutral": ("balanced_postures", "morning_mobility", "upper_body_flow"),
    "happiness": ("full_body_flow", "open_and_reach", "gentle_squat_flow"),
    "surprise": ("open_and_reach", "upper_body_flow"),
    "disgust": ("balanced_postures", "morning_mobility"),
    "fear": ("morning_mobility", "balanced_postures"),
    "contempt": ("upper_body_flow", "open_and_reach"),
}


def upgrade() -> None:
    table = op.create_table(
        "emotion_activity_recommendations",
        sa.Column("expression_key", sa.String(32),
                  sa.ForeignKey("expression_info.expression_key", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", sa.String(128),
                  sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("expression_key", "activity_id", name="pk_emotion_activity_recommendations"),
        sa.CheckConstraint("priority >= 0", name="ck_emotion_activity_recommendations_priority"),
    )
    op.create_index("ix_emotion_activity_recommendations_activity_id",
                    "emotion_activity_recommendations", ["activity_id"])
    connection = op.get_bind()
    existing = set(connection.execute(sa.text("SELECT id FROM activities")).scalars())
    rows = [
        {"expression_key": key, "activity_id": activity_id, "priority": priority}
        for key, activity_ids in SEED.items()
        for priority, activity_id in enumerate(activity_ids)
        if activity_id in existing
    ]
    if rows:
        op.bulk_insert(table, rows)


def downgrade() -> None:
    op.drop_table("emotion_activity_recommendations")
