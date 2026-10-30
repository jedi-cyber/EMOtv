"""Fases de la estación de un examen simulado en guided_runs.

- waiting: la estación se unió y espera el consentimiento; no se analiza nada.
- ready: la estación está calibrada y espera que el docente inicie el examen.
- exam: examen en curso; una fila cada medio segundo.
"""
from alembic import op

revision = "20261030_27"
down_revision = "20261029_26"
branch_labels = None
depends_on = None

BEFORE = ("phase IN ('pre_questionnaire', 'before_analyzer', 'calibration', "
          "'stimuli', 'post_questionnaire', 'live', 'finished', 'stopped')")
AFTER = ("phase IN ('pre_questionnaire', 'before_analyzer', 'calibration', "
         "'stimuli', 'post_questionnaire', 'live', 'waiting', 'ready', 'exam', 'finished', 'stopped')")


def upgrade() -> None:
    op.drop_constraint("ck_guided_runs_phase", "guided_runs", type_="check")
    op.create_check_constraint("ck_guided_runs_phase", "guided_runs", AFTER)


def downgrade() -> None:
    # Las estaciones que no terminaron quedan detenidas por quien conducía.
    op.execute("UPDATE guided_runs SET phase = 'stopped', stop_reason = 'conductor', view_token_hash = NULL "
               "WHERE phase IN ('waiting', 'ready', 'exam')")
    op.drop_constraint("ck_guided_runs_phase", "guided_runs", type_="check")
    op.create_check_constraint("ck_guided_runs_phase", "guided_runs", BEFORE)
