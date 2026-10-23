"""Sesión guiada: estado, capturas del protocolo, marcadores y lo que el
participante dice ver.

- guided_runs: fase y paso de cada sesión guiada (la base neutral no se guarda).
- expression_captures: expresión estimada, confianza, distribución, calidad,
  estímulo y tiempo desde su aparición. Sin imágenes ni datos de identidad.
- session_markers (nota cifrada) y verbal_responses (texto cifrado).
- protocol_steps.shown_before_analyzer: abstractas que se muestran antes de la
  calibración, sin capturas.
- ck_sessions_completed_result: una sesión con protocolo se completa sin una
  expresión única registrada.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261024_21"
down_revision = "20261023_20"
branch_labels = None
depends_on = None

OLD_COMPLETED = ("state <> 'completed' OR "
                 "(initial_emotion IS NOT NULL AND exercise_result IS NOT NULL AND "
                 "(exercise_result <> 'completed' OR "
                 "(activity_id IS NOT NULL AND exercise_duration_seconds IS NOT NULL)))")
NEW_COMPLETED = OLD_COMPLETED.replace("state <> 'completed' OR ", "state <> 'completed' OR protocol_id IS NOT NULL OR ", 1)


def _participant():
    return sa.Column("participant_id", sa.String(36), sa.ForeignKey("participants.id", ondelete="CASCADE"),
                     nullable=True)


def _session():
    return sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.add_column("protocol_steps", sa.Column("shown_before_analyzer", sa.Boolean(), nullable=False,
                                              server_default=sa.false()))
    op.drop_constraint("ck_sessions_completed_result", "sessions", type_="check")
    op.create_check_constraint("ck_sessions_completed_result", "sessions", NEW_COMPLETED)

    op.create_table(
        "guided_runs",
        sa.Column("session_id", sa.String(64), sa.ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True),
        _participant(),
        sa.Column("owner_user_id", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_capture_due", sa.Float(), nullable=True),
        sa.Column("steps_log", sa.JSON(), nullable=False),
        sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_token_hash", sa.String(64), nullable=True, unique=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.String(16), nullable=True),
        sa.CheckConstraint("phase IN ('confirmation', 'pre_questionnaire', 'before_analyzer', 'calibration', "
                           "'stimuli', 'post_questionnaire', 'finished', 'stopped')", name="ck_guided_runs_phase"),
        sa.CheckConstraint("(phase = 'stopped') = (stop_reason IS NOT NULL)", name="ck_guided_runs_stop_reason"),
        sa.CheckConstraint("stop_reason IS NULL OR stop_reason IN ('participant', 'guardian', 'conductor')",
                           name="ck_guided_runs_stop_reason_value"),
    )
    op.create_index("ix_guided_runs_participant_id", "guided_runs", ["participant_id"])
    op.create_index("ix_guided_runs_owner_user_id", "guided_runs", ["owner_user_id"])

    op.create_table(
        "expression_captures",
        sa.Column("id", sa.String(36), primary_key=True),
        _session(),
        _participant(),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("emotion_model_id", sa.String(128), nullable=False),
        sa.Column("emotion_model_version", sa.String(128), nullable=False),
        sa.Column("emotion", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("distribution", sa.JSON(), nullable=True),
        sa.Column("calibrated_emotion", sa.String(32), nullable=True),
        sa.Column("quality", sa.String(16), nullable=False),
        sa.Column("quality_issues", sa.JSON(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("stimulus_id", sa.String(36), sa.ForeignKey("stimuli.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("seconds_since_stimulus", sa.Float(), nullable=False),
        sa.CheckConstraint("quality IN ('good', 'flagged')", name="ck_expression_captures_quality"),
        sa.CheckConstraint("(emotion IS NULL) = (confidence IS NULL)", name="ck_expression_captures_emotion"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
                           name="ck_expression_captures_confidence"),
    )
    for column in ("session_id", "participant_id", "stimulus_id"):
        op.create_index(f"ix_expression_captures_{column}", "expression_captures", [column])

    op.create_table(
        "session_markers",
        sa.Column("id", sa.String(36), primary_key=True),
        _session(),
        _participant(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("note_encrypted", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column("recorded_by_user_id", sa.String(64), nullable=False),
        sa.CheckConstraint("kind IN ('distracted', 'laughed', 'asked_to_stop', 'cried', 'note')",
                           name="ck_session_markers_kind"),
    )
    for column in ("session_id", "participant_id"):
        op.create_index(f"ix_session_markers_{column}", "session_markers", [column])

    op.create_table(
        "verbal_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        _session(),
        _participant(),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("stimulus_id", sa.String(36), sa.ForeignKey("stimuli.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("text_encrypted", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_user_id", sa.String(64), nullable=False),
        sa.UniqueConstraint("session_id", "step_index", name="uq_verbal_responses_session_step"),
    )
    for column in ("session_id", "participant_id"):
        op.create_index(f"ix_verbal_responses_{column}", "verbal_responses", [column])


def downgrade() -> None:
    op.drop_table("verbal_responses")
    op.drop_table("session_markers")
    op.drop_table("expression_captures")
    op.drop_table("guided_runs")
    # Las sesiones guiadas completadas no cumplen la regla anterior: quedan canceladas.
    op.execute("UPDATE sessions SET state = 'cancelled' WHERE state = 'completed' AND initial_emotion IS NULL")
    op.drop_constraint("ck_sessions_completed_result", "sessions", type_="check")
    op.create_check_constraint("ck_sessions_completed_result", "sessions", OLD_COMPLETED)
    op.drop_column("protocol_steps", "shown_before_analyzer")
