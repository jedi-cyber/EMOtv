"""Store ordered activity steps."""
from alembic import op
import sqlalchemy as sa

revision = "20260921_08"
down_revision = "20260918_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("steps", sa.JSON(), nullable=False, server_default="[]"))
    activities = sa.table("activities", sa.column("id", sa.String), sa.column("name", sa.String),
        sa.column("description", sa.String), sa.column("required_posture", sa.String),
        sa.column("duration_seconds", sa.Float), sa.column("repetitions", sa.Integer),
        sa.column("steps", sa.JSON))
    catalog = [
        ("morning_mobility", "Movilidad suave", "Alterna brazos abiertos, arriba y manos en las caderas.", [("arms_open", "Abre los brazos a la altura de los hombros", 4), ("arms_up", "Eleva ambos brazos", 4), ("hands_on_hips", "Coloca las manos en las caderas", 4)]),
        ("upper_body_flow", "Movimiento de brazos", "Mueve los brazos al frente, abiertos y arriba.", [("arms_forward", "Extiende los brazos al frente", 4), ("arms_open", "Abre los brazos", 4), ("arms_up", "Eleva los brazos", 4)]),
        ("gentle_squat_flow", "Sentadilla y apertura", "Realiza una sentadilla suave y abre los brazos.", [("squat", "Flexiona las rodillas suavemente, sin forzarte", 3), ("arms_open", "Abre los brazos", 4), ("hands_on_hips", "Descansa con las manos en las caderas", 4)]),
        ("open_and_reach", "Abrir y alcanzar", "Abre, eleva y extiende los brazos al frente.", [("arms_open", "Abre los brazos", 4), ("arms_up", "Eleva los brazos", 4), ("arms_forward", "Extiende los brazos al frente", 4)]),
        ("balanced_postures", "Posturas equilibradas", "Alterna manos en las caderas, brazos al frente y abiertos.", [("hands_on_hips", "Coloca las manos en las caderas", 4), ("arms_forward", "Extiende los brazos al frente", 4), ("arms_open", "Abre los brazos", 4)]),
        ("full_body_flow", "Movimiento completo", "Combina brazos elevados, sentadilla y apertura.", [("arms_up", "Eleva los brazos", 4), ("squat", "Flexiona las rodillas suavemente", 3), ("arms_open", "Abre los brazos", 4)]),
    ]
    connection = op.get_bind()
    for activity_id, name, description, steps in catalog:
        if connection.execute(sa.select(activities.c.id).where(activities.c.id == activity_id)).first():
            continue
        connection.execute(activities.insert().values(id=activity_id, name=name, description=description,
            required_posture=steps[0][0], duration_seconds=steps[0][2], repetitions=1,
            steps=[dict(posture=posture, instruction=instruction, duration_seconds=duration)
                   for posture, instruction, duration in steps]))


def downgrade() -> None:
    op.drop_column("activities", "steps")
