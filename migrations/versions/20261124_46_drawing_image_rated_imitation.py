"""Imagen en el dibujo y «Juego: imita la cara».

- protocol_steps: un dibujo puede llevar una imagen (stimulus_id) que la persona
  mira antes de dibujar la emoción que siente. ck_protocol_steps_practice deja
  de exigir stimulus_id IS NULL en los dibujos.
- protocol_steps.conductor_rating: «Juego: imita la cara», una imitación que
  quien conduce valora al terminar. Lo valida el dominio (solo con imitate).
- practice_results.conductor_stars: esa valoración, de 1 a 5 estrellas. La
  restricción solo mira la propia columna.

Al volver atrás, los dibujos pierden su imagen, las imitaciones valoradas quedan
como «Haz la misma cara» y se borran las valoraciones. batch_alter_table permite
correr la misma migración en SQLite.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261124_46"
down_revision = "20261124_45"
branch_labels = None
depends_on = None

_PRACTICE = (
    "((kind = 'stimulus' AND target_expression IS NULL AND hold_seconds IS NULL AND option_count IS NULL)"
    " OR (kind = 'practice' AND target_expression IS NOT NULL AND hold_seconds IS NOT NULL AND hold_secon"
    'ds >= 1 AND hold_seconds < exposure_seconds AND capture_after_seconds = 0 AND option_count IS NULL) '
    "OR (kind = 'recognition' AND target_expression IS NOT NULL AND hold_seconds IS NULL AND option_count"
    " BETWEEN 2 AND 4 AND capture_after_seconds = 0) OR (kind = 'drawing' {drawing}AND target_expression "
    'IS NULL AND hold_seconds IS NULL AND option_count IS NULL AND capture_after_seconds = 0) OR (kind = '
    "'game' AND stimulus_id IS NULL AND target_expression IS NULL AND hold_seconds IS NULL AND option_cou"
    "nt BETWEEN 2 AND 4 AND capture_after_seconds = 0 AND game_type IN ('matching', 'similar') AND rounds"
    " BETWEEN 2 AND 6 AND game_stimulus_ids IS NOT NULL)) AND (situation IS NULL OR kind = 'recognition')"
    " AND (imitate = false OR (kind = 'practice' AND stimulus_id IS NOT NULL)) AND (kind = 'game' OR (gam"
    'e_type IS NULL AND rounds IS NULL AND game_stimulus_ids IS NULL))')
OLD_DRAWING = "AND stimulus_id IS NULL "
STARS = "conductor_stars IS NULL OR conductor_stars BETWEEN 1 AND 5"


def _practice(drawing: str) -> None:
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_constraint("ck_protocol_steps_practice", type_="check")
        batch.create_check_constraint("ck_protocol_steps_practice", _PRACTICE.format(drawing=drawing))


def upgrade() -> None:
    _practice("")
    with op.batch_alter_table("protocol_steps") as batch:
        batch.add_column(sa.Column("conductor_rating", sa.Boolean(), nullable=False,
                                   server_default=sa.text("false")))
    with op.batch_alter_table("practice_results") as batch:
        batch.add_column(sa.Column("conductor_stars", sa.Integer(), nullable=True))
        batch.create_check_constraint("ck_practice_results_conductor_stars", STARS)


def downgrade() -> None:
    with op.batch_alter_table("practice_results") as batch:
        batch.drop_constraint("ck_practice_results_conductor_stars", type_="check")
        batch.drop_column("conductor_stars")
    with op.batch_alter_table("protocol_steps") as batch:
        batch.drop_column("conductor_rating")
    op.execute("UPDATE protocol_steps SET stimulus_id = NULL WHERE kind = 'drawing'")
    _practice(OLD_DRAWING)
