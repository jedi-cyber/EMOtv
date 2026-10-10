"""Avance de actividades secuenciales en la sesión.

Agrega pasos completados, total de pasos (pasos × repeticiones) y repeticiones.
Las filas existentes quedan con los tres valores nulos: no se reconstruye un
avance que no se registró.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_14"
down_revision = "20261009_13"
branch_labels = None
depends_on = None

PROGRESS = (
    "(exercise_steps_completed IS NULL AND exercise_steps_total IS NULL "
    "AND exercise_repetitions IS NULL) OR "
    "(exercise_repetitions >= 1 AND exercise_steps_total >= exercise_repetitions "
    "AND exercise_steps_completed >= 0 "
    "AND exercise_steps_completed <= exercise_steps_total)"
)


def upgrade() -> None:
    op.add_column("sessions", sa.Column("exercise_steps_completed", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("exercise_steps_total", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("exercise_repetitions", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_sessions_exercise_progress", "sessions", PROGRESS)


def downgrade() -> None:
    op.drop_constraint("ck_sessions_exercise_progress", "sessions", type_="check")
    op.drop_column("sessions", "exercise_repetitions")
    op.drop_column("sessions", "exercise_steps_total")
    op.drop_column("sessions", "exercise_steps_completed")
