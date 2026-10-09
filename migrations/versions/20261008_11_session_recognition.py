"""Expresión registrada por el estudiante: estado recognized y recognized_at.

Las filas existentes siguen siendo válidas: recognized_at queda nulo (no se
inventa la hora de un reconocimiento que no se registró así) y las nuevas
restricciones solo amplían las anteriores.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_11"
down_revision = "20261006_10"
branch_labels = None
depends_on = None

OLD_STATE = "state IN ('created', 'in_progress', 'completed', 'cancelled')"
OLD_TIMESTAMP = (
    "(state IN ('completed', 'cancelled') AND completed_at IS NOT NULL) OR "
    "(state IN ('created', 'in_progress') AND completed_at IS NULL)"
)
OLD_RESULT = (
    "state <> 'completed' OR "
    "(initial_emotion IS NOT NULL AND activity_id IS NOT NULL AND "
    "exercise_result IS NOT NULL AND exercise_duration_seconds IS NOT NULL)"
)
NEW_STATE = "state IN ('created', 'in_progress', 'recognized', 'completed', 'cancelled')"
NEW_TIMESTAMP = (
    "(state IN ('completed', 'cancelled') AND completed_at IS NOT NULL) OR "
    "(state IN ('created', 'in_progress', 'recognized') AND completed_at IS NULL)"
)
NEW_RESULT = (
    "state <> 'completed' OR "
    "(initial_emotion IS NOT NULL AND exercise_result IS NOT NULL AND "
    "(exercise_result <> 'completed' OR "
    "(activity_id IS NOT NULL AND exercise_duration_seconds IS NOT NULL)))"
)
RECOGNITION = (
    "(recognized_at IS NULL OR (initial_emotion IS NOT NULL AND recognized_at >= started_at)) AND "
    "(state <> 'recognized' OR recognized_at IS NOT NULL)"
)


def _replace(name: str, condition: str) -> None:
    op.drop_constraint(name, "sessions", type_="check")
    op.create_check_constraint(name, "sessions", condition)


def upgrade() -> None:
    op.add_column("sessions", sa.Column("recognized_at", sa.DateTime(timezone=True), nullable=True))
    _replace("ck_sessions_state_valid", NEW_STATE)
    _replace("ck_sessions_completion_timestamp", NEW_TIMESTAMP)
    _replace("ck_sessions_completed_result", NEW_RESULT)
    op.create_check_constraint("ck_sessions_recognition", "sessions", RECOGNITION)


def downgrade() -> None:
    # Las sesiones del flujo nuevo no caben en el esquema anterior; no se
    # borran ni se alteran en silencio.
    incompatible = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM sessions WHERE state = 'recognized' OR "
        "(state = 'completed' AND (activity_id IS NULL OR exercise_duration_seconds IS NULL))"
    )).scalar_one()
    if incompatible:
        raise RuntimeError(
            f"{incompatible} sesión(es) usan el reconocimiento registrado o terminaron "
            "sin actividad; respáldalas y resuélvelas antes de revertir esta migración"
        )
    op.drop_constraint("ck_sessions_recognition", "sessions", type_="check")
    _replace("ck_sessions_completed_result", OLD_RESULT)
    _replace("ck_sessions_completion_timestamp", OLD_TIMESTAMP)
    _replace("ck_sessions_state_valid", OLD_STATE)
    op.drop_column("sessions", "recognized_at")
