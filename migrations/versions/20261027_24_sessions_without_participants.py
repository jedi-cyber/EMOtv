"""Sesiones sin participantes y protocolos con público.

- Elimina participants, participant_authorizations y participant_deletion_records,
  y las columnas participant_id de sesiones, sesión guiada, capturas, marcadores,
  respuestas, cuestionarios y reportes. La sesión conserva sus capturas,
  respuestas, marcadores y reporte.
- sessions: código aleatorio (S-XXXXXX; se genera para las filas existentes),
  fecha de la confirmación de autorización y solicitud de eliminación. El
  público pasa a 'propia', 'adulto' e 'infantil'.
- session_deletion_records: acta de eliminación por sesión, sin datos personales.
- guided_runs: sin fase de confirmación (se confirma al iniciar) y con la fase
  live del aplicativo móvil sin protocolo.
- expression_captures.stimulus_id admite nulo (registro sin protocolo).

Al aplicarla solo había datos de desarrollo: los participantes y sus
autorizaciones se descartan.
"""
import secrets

from alembic import op
import sqlalchemy as sa

revision = "20261027_24"
down_revision = "20261026_23"
branch_labels = None
depends_on = None

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LINKED = ("guided_runs", "expression_captures", "session_markers", "verbal_responses", "questionnaire_responses",
          "session_reports", "report_comments", "report_events")


def _code(used: set[str]) -> str:
    while True:
        code = "S-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if code not in used:
            used.add(code)
            return code


def upgrade() -> None:
    for table in LINKED:
        op.drop_column(table, "participant_id")
    op.drop_column("sessions", "participant_id")
    op.drop_table("participant_authorizations")
    op.drop_table("participants")
    op.drop_table("participant_deletion_records")

    op.drop_constraint("ck_sessions_session_type", "sessions", type_="check")
    op.execute("UPDATE sessions SET session_type = 'adulto' WHERE session_type = 'participante_adulto'")
    op.execute("UPDATE sessions SET session_type = 'infantil' WHERE session_type = 'participante_infantil'")
    op.create_check_constraint("ck_sessions_session_type", "sessions", "session_type IN ('propia', 'adulto', 'infantil')")

    op.add_column("sessions", sa.Column("code", sa.String(16), nullable=True))
    op.add_column("sessions", sa.Column("authorization_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sessions", sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sessions", sa.Column("deletion_requested_by_user_id", sa.String(64), nullable=True))
    connection = op.get_bind()
    used: set[str] = set()
    for (session_id,) in connection.execute(sa.text("SELECT id FROM sessions")).fetchall():
        connection.execute(sa.text("UPDATE sessions SET code = :code WHERE id = :id"),
                           {"code": _code(used), "id": session_id})
    op.create_unique_constraint("uq_sessions_code", "sessions", ["code"])
    op.create_check_constraint(
        "ck_sessions_deletion_request", "sessions",
        "(deletion_requested_at IS NULL AND deletion_requested_by_user_id IS NULL) OR "
        "(deletion_requested_at IS NOT NULL AND deletion_requested_by_user_id IS NOT NULL)")

    op.create_table(
        "session_deletion_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_code", sa.String(16), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_by_user_id", sa.String(64), nullable=True),
        sa.Column("requested_by_user_id", sa.String(64), nullable=True),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_session_deletion_records_executed_by_user_id", "session_deletion_records",
                    ["executed_by_user_id"])
    op.create_index("ix_session_deletion_records_requested_by_user_id", "session_deletion_records",
                    ["requested_by_user_id"])

    op.drop_constraint("ck_guided_runs_phase", "guided_runs", type_="check")
    op.execute("UPDATE guided_runs SET phase = 'stopped', stop_reason = 'conductor' WHERE phase = 'confirmation'")
    op.create_check_constraint(
        "ck_guided_runs_phase", "guided_runs",
        "phase IN ('pre_questionnaire', 'before_analyzer', 'calibration', 'stimuli', 'post_questionnaire', "
        "'live', 'finished', 'stopped')")
    op.alter_column("expression_captures", "stimulus_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    """Restaura la estructura anterior, sin datos de participantes."""
    op.execute("DELETE FROM expression_captures WHERE stimulus_id IS NULL")
    op.alter_column("expression_captures", "stimulus_id", existing_type=sa.String(36), nullable=False)
    op.drop_constraint("ck_guided_runs_phase", "guided_runs", type_="check")
    op.execute("UPDATE guided_runs SET phase = 'stopped', stop_reason = 'conductor' WHERE phase = 'live'")
    op.create_check_constraint(
        "ck_guided_runs_phase", "guided_runs",
        "phase IN ('confirmation', 'pre_questionnaire', 'before_analyzer', 'calibration', 'stimuli', "
        "'post_questionnaire', 'finished', 'stopped')")
    op.drop_table("session_deletion_records")
    op.drop_constraint("ck_sessions_deletion_request", "sessions", type_="check")
    op.drop_constraint("uq_sessions_code", "sessions", type_="unique")
    for column in ("deletion_requested_by_user_id", "deletion_requested_at", "authorization_confirmed_at", "code"):
        op.drop_column("sessions", column)
    op.drop_constraint("ck_sessions_session_type", "sessions", type_="check")
    op.execute("UPDATE sessions SET session_type = 'participante_adulto' WHERE session_type = 'adulto'")
    op.execute("UPDATE sessions SET session_type = 'participante_infantil' WHERE session_type = 'infantil'")
    op.create_check_constraint("ck_sessions_session_type", "sessions",
                               "session_type IN ('propia', 'participante_adulto', 'participante_infantil')")

    op.create_table(
        "participant_deletion_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("participant_code", sa.String(16), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_by_user_id", sa.String(64), nullable=True),
        sa.Column("requested_by_user_id", sa.String(64), nullable=True),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "participants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("registered_by_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("notes_encrypted", sa.Text(), nullable=True),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_requested_by_user_id", sa.String(64), nullable=True),
        sa.Column("age_years", sa.Integer(), nullable=True),
        sa.Column("authorization_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('adult', 'child')", name="ck_participants_kind"),
    )
    op.create_table(
        "participant_authorizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("participant_id", sa.String(36), sa.ForeignKey("participants.id", ondelete="CASCADE"),
                  nullable=False, index=True),
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
    )
    # En los reportes era obligatoria; sin participantes que restaurar queda nula.
    for table in ("sessions", *LINKED):
        op.add_column(table, sa.Column("participant_id", sa.String(36),
                                       sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=True))
        op.create_index(f"ix_{table}_participant_id", table, ["participant_id"])
