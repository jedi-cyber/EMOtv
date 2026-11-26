"""El dibujo de un protocolo ya no pregunta qué emoción se quiso dibujar.

- drawing_results: un dibujo terminado («Terminé») se registra sin emoción.
  ck_drawing_results_answered deja de exigir chosen_expression en los pasos
  terminados; las sesiones anteriores conservan la emoción que se señaló. La
  restricción solo mira columnas de la propia tabla.

Al volver atrás, la versión anterior exige una emoción en cada dibujo terminado:
los dibujos terminados sin emoción se borran (no hay una emoción que poner sin
inventarla). batch_alter_table permite correr la misma migración en SQLite.
"""
from alembic import op

revision = "20261124_48"
down_revision = "20261124_47"
branch_labels = None
depends_on = None

NEW = ("(outcome = 'answered' OR chosen_expression IS NULL) "
       "AND (outcome = 'answered') = (seconds_to_answer IS NOT NULL) "
       "AND (outcome = 'answered') = (answered_by IS NOT NULL)")
OLD = ("(outcome = 'answered') = (chosen_expression IS NOT NULL) "
       "AND (outcome = 'answered') = (seconds_to_answer IS NOT NULL) "
       "AND (outcome = 'answered') = (answered_by IS NOT NULL)")


def _check(text: str) -> None:
    with op.batch_alter_table("drawing_results") as batch:
        batch.drop_constraint("ck_drawing_results_answered", type_="check")
        batch.create_check_constraint("ck_drawing_results_answered", text)


def upgrade() -> None:
    _check(NEW)


def downgrade() -> None:
    op.execute("DELETE FROM drawing_results WHERE outcome = 'answered' AND chosen_expression IS NULL")
    _check(OLD)
