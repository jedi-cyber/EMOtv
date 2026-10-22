"""Participantes con edad, autorizaciones firmadas, banco de estímulos y protocolos.

- participants.age_years (nulo solo en participantes registrados antes de pedir
  la edad) y participants.authorization_revoked_at (marca de retiro).
- participant_authorizations: formato firmado en papel, sin datos de quien firma.
- stimuli: imágenes del banco (nunca fotos de participantes), sin metadatos.
- protocols y protocol_steps: versiones de cada protocolo y sus estímulos en orden.
- sessions.protocol_id: versión del protocolo aplicado.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261022_19"
down_revision = "20261021_18"
branch_labels = None
depends_on = None

APPROVAL = ("(approved_at IS NULL AND approved_by_user_id IS NULL) OR "
            "(approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)")


def upgrade() -> None:
    op.add_column("participants", sa.Column("age_years", sa.Integer(), nullable=True))
    op.add_column("participants", sa.Column("authorization_revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_participants_age_matches_kind", "participants",
        "age_years IS NULL OR (kind = 'adult' AND age_years BETWEEN 18 AND 120) OR "
        "(kind = 'child' AND age_years BETWEEN 1 AND 17)")

    op.create_table(
        "participant_authorizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("participant_id", sa.String(36), sa.ForeignKey("participants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("form_version", sa.String(64), nullable=False),
        sa.Column("signed_on", sa.Date(), nullable=False),
        sa.Column("grantor", sa.String(16), nullable=False),
        sa.Column("participation", sa.Boolean(), nullable=False),
        sa.Column("camera", sa.Boolean(), nullable=False),
        sa.Column("child_assent", sa.Boolean(), nullable=True),
        sa.Column("recorded_by_user_id", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(64), nullable=True),
        sa.Column("revoked_party", sa.String(16), nullable=True),
        sa.Column("revoked_scope", sa.String(16), nullable=True),
        sa.CheckConstraint("grantor IN ('participant', 'guardian')", name="ck_participant_authorizations_grantor"),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL AND revoked_party IS NULL "
            "AND revoked_scope IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL "
            "AND revoked_party IN ('participant', 'guardian') "
            "AND revoked_scope IN ('participation', 'camera', 'assent'))",
            name="ck_participant_authorizations_revocation"),
    )
    op.create_index("ix_participant_authorizations_participant_id", "participant_authorizations",
                    ["participant_id"])

    op.create_table(
        "stimuli",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("expected_expression", sa.String(32), nullable=True),
        sa.Column("intensity", sa.String(16), nullable=False),
        sa.Column("min_age", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(500), nullable=False),
        sa.Column("license", sa.String(300), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("owner_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("image", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint("kind IN ('emotional', 'abstract')", name="ck_stimuli_kind"),
        sa.CheckConstraint("intensity IN ('mild', 'moderate')", name="ck_stimuli_intensity"),
        sa.CheckConstraint("scope IN ('group', 'institution')", name="ck_stimuli_scope"),
        sa.CheckConstraint("min_age BETWEEN 1 AND 99", name="ck_stimuli_min_age"),
        sa.CheckConstraint("(kind = 'emotional' AND expected_expression IS NOT NULL) OR "
                           "(kind = 'abstract' AND expected_expression IS NULL)",
                           name="ck_stimuli_expected_expression"),
        sa.CheckConstraint(APPROVAL, name="ck_stimuli_approval"),
    )
    op.create_index("ix_stimuli_owner_user_id", "stimuli", ["owner_user_id"])

    op.create_table(
        "protocols",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("for_children", sa.Boolean(), nullable=False),
        sa.Column("pre_questionnaire_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(64), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("family_id", "version", name="uq_protocols_family_version"),
        sa.CheckConstraint("version >= 1", name="ck_protocols_version"),
        sa.CheckConstraint(APPROVAL, name="ck_protocols_approval"),
    )
    op.create_index("ix_protocols_family_id", "protocols", ["family_id"])
    op.create_index("ix_protocols_owner_user_id", "protocols", ["owner_user_id"])

    op.create_table(
        "protocol_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("protocol_id", sa.String(36), sa.ForeignKey("protocols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("stimulus_id", sa.String(36), sa.ForeignKey("stimuli.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("exposure_seconds", sa.Integer(), nullable=False),
        sa.Column("capture_after_seconds", sa.Integer(), nullable=False),
        sa.Column("record_verbal_response", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("protocol_id", "position", name="uq_protocol_steps_position"),
        sa.CheckConstraint("exposure_seconds BETWEEN 1 AND 120", name="ck_protocol_steps_exposure"),
        sa.CheckConstraint("capture_after_seconds >= 0 AND capture_after_seconds <= exposure_seconds",
                           name="ck_protocol_steps_capture"),
    )
    op.create_index("ix_protocol_steps_protocol_id", "protocol_steps", ["protocol_id"])
    op.create_index("ix_protocol_steps_stimulus_id", "protocol_steps", ["stimulus_id"])

    op.add_column("sessions", sa.Column("protocol_id", sa.String(36),
                                        sa.ForeignKey("protocols.id", ondelete="RESTRICT"), nullable=True))
    op.create_index("ix_sessions_protocol_id", "sessions", ["protocol_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_protocol_id", "sessions")
    op.drop_column("sessions", "protocol_id")
    op.drop_table("protocol_steps")
    op.drop_table("protocols")
    op.drop_table("stimuli")
    op.drop_table("participant_authorizations")
    op.drop_constraint("ck_participants_age_matches_kind", "participants", type_="check")
    op.drop_column("participants", "authorization_revoked_at")
    op.drop_column("participants", "age_years")
