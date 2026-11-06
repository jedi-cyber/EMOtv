"""Explicación sencilla por expresión (docs/adaptacion-psicoeducacion.md, bloque 3).

- expression_info.child_explanation: una oración corta que describe la cara de
  la emoción. La lee la persona al terminar un paso «¿Qué emoción es?».
- Los textos iniciales son borradores redactados por el equipo; ningún LLM los
  genera. Como agregan contenido sin revisar, una fila ya revisada vuelve a
  borrador: un cambio nunca queda como revisado sin una nueva revisión.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_37"
down_revision = "20261106_36"
branch_labels = None
depends_on = None

# Describen la cara; no dicen qué siente la persona ni la valoran.
SEED = {
    "neutral": "En una cara tranquila, las cejas, los ojos y la boca están relajados.",
    "happiness": "En la alegría, la boca sonríe y las mejillas suben.",
    "surprise": "En la sorpresa, las cejas suben, los ojos se abren mucho y la boca se abre.",
    "sadness": "En la tristeza, las cejas suben en el centro y las puntas de la boca bajan.",
    "anger": "En el enojo, las cejas bajan y se juntan, y la boca se aprieta.",
    "disgust": "En el asco, la nariz se arruga y el labio de arriba sube.",
    "fear": "En el miedo, las cejas suben y se juntan, y los ojos se abren mucho.",
    "contempt": "En el desprecio, sube solo un lado de la boca.",
}


def upgrade() -> None:
    with op.batch_alter_table("expression_info") as batch:
        batch.add_column(sa.Column("child_explanation", sa.String(200), nullable=False, server_default=""))
    update = sa.text(
        "UPDATE expression_info SET child_explanation = :text, review_status = 'draft', "
        "reviewed_at = NULL, reviewed_by_user_id = NULL WHERE expression_key = :key")
    for key, text in SEED.items():
        op.execute(update.bindparams(key=key, text=text))


def downgrade() -> None:
    with op.batch_alter_table("expression_info") as batch:
        batch.drop_column("child_explanation")
