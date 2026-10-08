"""Catálogo informativo de expresiones (textos fijos y revisables, en borrador).

Los textos los redacta el equipo y deben revisarlos profesionales de Psicología
antes de marcarse como "reviewed". Ningún LLM los genera ni los completa.
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "20261008_12"
down_revision = "20261008_11"
branch_labels = None
depends_on = None

_LIMIT_CONTEXT = (
    "La cultura, el contexto, la iluminación y el ángulo de la cámara influyen en el reconocimiento."
)

SEED = (
    {
        "expression_key": "neutral",
        "label_es": "Neutral",
        "what_it_is": (
            "La expresión neutral es un rostro relajado en el que no destaca ninguna emoción en particular. "
            "Es el punto de partida habitual desde el que se forman las demás expresiones."
        ),
        "why_it_occurs": (
            "Es la expresión más frecuente en la vida diaria, por ejemplo al escuchar, leer o concentrarse en una tarea. "
            "Suele aparecer cuando no hay un estímulo que provoque una reacción emocional visible. "
            "También puede presentarse cuando las personas regulan o no muestran lo que experimentan."
        ),
        "facial_cues": (
            "Las cejas están en posición de reposo y la frente no muestra arrugas marcadas. "
            "Los ojos están abiertos de forma natural y los labios cerrados o apenas separados, sin tensión. "
            "Puede mantenerse durante periodos largos sin cambios."
        ),
        "practice_tip": (
            "Relaja la frente, las mejillas y la mandíbula, y mira al frente durante unos segundos. "
            "Observa en la lectura en vivo cómo cambia la estimación al pasar de otra expresión a un rostro relajado."
        ),
        "limitation_note": (
            "Un rostro en reposo puede leerse como neutral, tristeza leve o enojo leve según la forma natural de cada cara. "
            f"{_LIMIT_CONTEXT} "
            "Una expresión compatible con neutralidad no indica ausencia de emociones."
        ),
    },
    {
        "expression_key": "happiness",
        "label_es": "Felicidad",
        "what_it_is": (
            "La felicidad es una emoción asociada al bienestar, al disfrute y a la satisfacción. "
            "En el rostro suele mostrarse con una sonrisa."
        ),
        "why_it_occurs": (
            "En general aparece ante logros, encuentros agradables, buenas noticias o actividades que resultan placenteras. "
            "Cumple una función social: facilita el acercamiento, la cooperación y los vínculos con otras personas."
        ),
        "facial_cues": (
            "Las comisuras de los labios se elevan y las mejillas suben. "
            "En la sonrisa espontánea se forman pequeñas arrugas junto a los ojos. "
            "Suele durar desde menos de un segundo hasta varios segundos."
        ),
        "practice_tip": (
            "Sonríe elevando las comisuras y deja que las mejillas suban hasta notar un ligero cierre de los ojos. "
            "Compara en la lectura en vivo una sonrisa solo con la boca y otra que también involucra los ojos."
        ),
        "limitation_note": (
            "Una sonrisa no siempre acompaña a la felicidad, porque también aparece por cortesía, nerviosismo o costumbre social. "
            f"{_LIMIT_CONTEXT} "
            "El sistema solo indica una expresión compatible con felicidad."
        ),
    },
    {
        "expression_key": "surprise",
        "label_es": "Sorpresa",
        "what_it_is": (
            "La sorpresa es una reacción breve ante algo inesperado. "
            "Puede dar paso a otras emociones, como alegría o miedo, según lo que ocurra después."
        ),
        "why_it_occurs": (
            "Suele presentarse ante sucesos repentinos o que no coinciden con lo que se esperaba, como un ruido, una noticia o un cambio súbito. "
            "Su función general es orientar la atención y preparar a la persona para procesar la nueva información."
        ),
        "facial_cues": (
            "Las cejas se elevan y se curvan, y en la frente aparecen arrugas horizontales. "
            "Los ojos se abren más de lo habitual y la mandíbula puede caer, dejando la boca entreabierta. "
            "Es una de las expresiones más breves, normalmente de uno o dos segundos."
        ),
        "practice_tip": (
            "Eleva las cejas, abre bien los ojos y separa ligeramente los labios, sin tensar la parte inferior del rostro. "
            "Prueba a diferenciarla del miedo, en el que las cejas además se juntan."
        ),
        "limitation_note": (
            "La sorpresa y el miedo comparten rasgos y pueden confundirse en una imagen fija. "
            f"{_LIMIT_CONTEXT} "
            "El sistema solo indica una expresión compatible con sorpresa."
        ),
    },
    {
        "expression_key": "sadness",
        "label_es": "Tristeza",
        "what_it_is": (
            "La tristeza es una emoción relacionada con la pérdida, la decepción o la falta de algo valorado. "
            "En el rostro suele mostrarse con un gesto de decaimiento."
        ),
        "why_it_occurs": (
            "En general aparece ante pérdidas, despedidas, fracasos o situaciones que no salen como se esperaba. "
            "Cumple funciones como favorecer la reflexión y comunicar a otras personas que puede necesitarse apoyo."
        ),
        "facial_cues": (
            "Los extremos internos de las cejas se elevan y se juntan, y a veces forman un pliegue en la frente. "
            "Los párpados superiores pueden caer y las comisuras de los labios descienden. "
            "Puede mantenerse varios segundos y suele ser menos intensa que otras expresiones."
        ),
        "practice_tip": (
            "Eleva solo la parte interna de las cejas y baja ligeramente las comisuras de los labios. "
            "Observa en la lectura en vivo que es una expresión sutil y que el modelo puede necesitar unos segundos para estabilizarla."
        ),
        "limitation_note": (
            "La tristeza suele ser sutil y los modelos la confunden con frecuencia con una expresión neutral. "
            f"{_LIMIT_CONTEXT} "
            "El sistema solo indica una expresión compatible con tristeza."
        ),
    },
    {
        "expression_key": "anger",
        "label_es": "Enojo",
        "what_it_is": (
            "El enojo es una emoción relacionada con la frustración o con percibir algo como injusto o como un obstáculo. "
            "En el rostro se muestra con tensión, sobre todo en las cejas y los labios."
        ),
        "why_it_occurs": (
            "Suele presentarse cuando algo impide alcanzar una meta o cuando se percibe una ofensa o una injusticia. "
            "Su función general es movilizar energía para enfrentar el obstáculo y comunicar un límite a los demás."
        ),
        "facial_cues": (
            "Las cejas descienden y se juntan, formando líneas verticales entre ellas. "
            "La mirada se vuelve fija, los párpados se tensan y los labios se aprietan o se separan mostrando los dientes. "
            "Puede ser breve o mantenerse mientras dura la situación."
        ),
        "practice_tip": (
            "Baja y junta las cejas, fija la mirada y aprieta suavemente los labios. "
            "Compara en la lectura en vivo cómo cambia la estimación si relajas solo los labios."
        ),
        "limitation_note": (
            "Una mirada concentrada o el ceño fruncido por la luz pueden leerse como enojo. "
            f"{_LIMIT_CONTEXT} "
            "El sistema solo indica una expresión compatible con enojo."
        ),
    },
    {
        "expression_key": "disgust",
        "label_es": "Desagrado",
        "what_it_is": (
            "El desagrado, también llamado asco, es una reacción de rechazo ante algo que resulta desagradable. "
            "Puede referirse a olores o sabores, y también a situaciones y conductas."
        ),
        "why_it_occurs": (
            "En general aparece ante estímulos percibidos como sucios, en mal estado o inapropiados. "
            "Su función general es proteger a la persona, alejándola de aquello que podría ser dañino."
        ),
        "facial_cues": (
            "La nariz se arruga y el labio superior se eleva. "
            "Las mejillas suben y las cejas pueden bajar ligeramente. "
            "Suele ser una expresión breve."
        ),
        "practice_tip": (
            "Arruga la nariz y eleva el labio superior, como ante un olor desagradable. "
            "Fíjate en que el gesto se concentra en el centro del rostro."
        ),
        "limitation_note": (
            "El desagrado tiene pocos ejemplos en los datos con que se entrenan los modelos, por lo que su estimación es menos fiable. "
            f"{_LIMIT_CONTEXT} "
            "El sistema solo indica una expresión compatible con desagrado."
        ),
    },
    {
        "expression_key": "fear",
        "label_es": "Miedo",
        "what_it_is": (
            "El miedo es una emoción de alerta ante un peligro real o percibido. "
            "Prepara a la persona para reaccionar con rapidez."
        ),
        "why_it_occurs": (
            "Suele presentarse ante amenazas, situaciones desconocidas o la posibilidad de un daño. "
            "Su función general es proteger, aumentando la atención y preparando respuestas como alejarse o pedir ayuda."
        ),
        "facial_cues": (
            "Las cejas se elevan y a la vez se juntan, y los párpados superiores suben mostrando más blanco del ojo. "
            "Los labios se estiran horizontalmente hacia los lados. "
            "Puede durar desde un instante hasta varios segundos."
        ),
        "practice_tip": (
            "Eleva y junta las cejas, abre mucho los ojos y estira los labios hacia los lados. "
            "Compárala con la sorpresa, en la que la boca se abre sin estirarse."
        ),
        "limitation_note": (
            "El miedo y la sorpresa comparten rasgos y suelen confundirse. "
            f"{_LIMIT_CONTEXT} "
            "El sistema solo indica una expresión compatible con miedo."
        ),
    },
    {
        "expression_key": "contempt",
        "label_es": "Desprecio",
        "what_it_is": (
            "El desprecio es una emoción relacionada con considerar a alguien o algo como inferior. "
            "Es la única expresión básica que suele mostrarse en un solo lado del rostro."
        ),
        "why_it_occurs": (
            "En general aparece cuando se juzga una conducta o a una persona como inferior o reprobable. "
            "Su función social es marcar distancia o desaprobación."
        ),
        "facial_cues": (
            "Una de las comisuras de los labios se tensa y se eleva hacia un lado, formando una media sonrisa asimétrica. "
            "La mirada puede dirigirse ligeramente hacia abajo. "
            "Suele ser breve."
        ),
        "practice_tip": (
            "Eleva y tensa una sola comisura de los labios, manteniendo el resto del rostro relajado. "
            "Observa la diferencia con una sonrisa, que suele ser simétrica."
        ),
        "limitation_note": (
            "El desprecio es poco frecuente en los datos de entrenamiento y puede confundirse con una sonrisa leve o con una expresión neutral. "
            f"{_LIMIT_CONTEXT} "
            "El sistema solo indica una expresión compatible con desprecio."
        ),
    },
)


def upgrade() -> None:
    table = op.create_table(
        "expression_info",
        sa.Column("expression_key", sa.String(32), primary_key=True),
        sa.Column("label_es", sa.String(60), nullable=False),
        sa.Column("what_it_is", sa.String(1200), nullable=False),
        sa.Column("why_it_occurs", sa.String(1200), nullable=False),
        sa.Column("facial_cues", sa.String(1200), nullable=False),
        sa.Column("practice_tip", sa.String(1200), nullable=False),
        sa.Column("limitation_note", sa.String(1200), nullable=False),
        sa.Column("review_status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("reviewed_by_user_id", sa.String(64),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("review_status IN ('draft', 'reviewed')", name="ck_expression_info_review_status"),
        sa.CheckConstraint(
            "(review_status = 'draft' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL) OR "
            "(review_status = 'reviewed' AND reviewed_at IS NOT NULL)",
            name="ck_expression_info_review_fields",
        ),
    )
    now = datetime.now(timezone.utc)
    # Todo el contenido inicial queda en borrador hasta la revisión de Psicología.
    op.bulk_insert(table, [{**row, "review_status": "draft", "updated_at": now} for row in SEED])


def downgrade() -> None:
    op.drop_table("expression_info")
