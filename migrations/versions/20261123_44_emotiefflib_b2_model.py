"""EmotiEffLib enet_b2_8 puede ser el modelo local predeterminado.

Amplía la restricción de local_model_settings.default_model_id con
'emotiefflib_enet_b2_8'. Al bajar, una configuración que lo use vuelve a
HSEmotion antes de restaurar la restricción anterior.
"""
from alembic import op

revision = "20261123_44"
down_revision = "20261107_43"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_local_model_settings_default_model"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, "local_model_settings", type_="check")
    op.create_check_constraint(
        CONSTRAINT, "local_model_settings",
        "default_model_id IN ('hsemotion_enet_b0_8_best_afew', 'emotiefflib_enet_b2_8', 'ferplus_onnx')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE local_model_settings SET default_model_id = 'hsemotion_enet_b0_8_best_afew' "
        "WHERE default_model_id = 'emotiefflib_enet_b2_8'"
    )
    op.drop_constraint(CONSTRAINT, "local_model_settings", type_="check")
    op.create_check_constraint(
        CONSTRAINT, "local_model_settings",
        "default_model_id IN ('hsemotion_enet_b0_8_best_afew', 'ferplus_onnx')",
    )
