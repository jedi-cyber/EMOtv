"""Papeles, grupos de un solo docente, participantes, auditoría y compromiso.

- users.role: el antiguo "admin" (soporte técnico) pasa a "superadmin"; "admin"
  queda para la persona con cargo superior en la Facultad. users.password_reset_at
  guarda el último restablecimiento para avisar en el siguiente ingreso.
- psychologist_assignments: un usuario tiene un solo docente. Si un usuario
  tenía varios, se conserva la asignación más reciente y el resto se elimina;
  la migración informa solo la cantidad (sin identificadores ni correos).
- participants (sin nombre, DNI ni foto; notas cifradas), commitment_acceptances,
  access_audit y participant_deletion_records.
- sessions.owner_user_id (quien conduce; las sesiones existentes toman la cuenta
  del perfil students) y sessions.participant_id.
"""
import logging

from alembic import op
import sqlalchemy as sa

revision = "20261021_18"
down_revision = "20261019_17"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint("ck_users_role_valid", "users", type_="check")
    op.execute("UPDATE users SET role = 'superadmin' WHERE role = 'admin'")
    op.create_check_constraint("ck_users_role_valid", "users",
                               "role IN ('student','psychologist','admin','superadmin')")
    op.add_column("users", sa.Column("password_reset_at", sa.DateTime(timezone=True), nullable=True))

    # Un solo docente por usuario: conserva la asignación más reciente.
    duplicated = bind.execute(sa.text(
        "SELECT count(*) FROM (SELECT student_id FROM psychologist_assignments "
        "GROUP BY student_id HAVING count(*) > 1) AS t")).scalar() or 0
    removed = bind.execute(sa.text(
        "DELETE FROM psychologist_assignments AS a WHERE EXISTS ("
        "SELECT 1 FROM psychologist_assignments AS b WHERE b.student_id = a.student_id AND "
        "(b.assigned_at > a.assigned_at OR (b.assigned_at = a.assigned_at "
        "AND b.psychologist_user_id > a.psychologist_user_id)))")).rowcount
    if duplicated:
        logger.warning("Usuarios con varios docentes: %s; asignaciones antiguas eliminadas: %s",
                       duplicated, removed)
    op.create_unique_constraint("uq_psychologist_assignments_student_id", "psychologist_assignments",
                                ["student_id"])

    op.create_table(
        "participants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("registered_by_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes_encrypted", sa.Text(), nullable=True),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_requested_by_user_id", sa.String(64), nullable=True),
        sa.CheckConstraint("kind IN ('adult', 'child')", name="ck_participants_kind"),
        sa.CheckConstraint(
            "(deletion_requested_at IS NULL AND deletion_requested_by_user_id IS NULL) OR "
            "(deletion_requested_at IS NOT NULL AND deletion_requested_by_user_id IS NOT NULL)",
            name="ck_participants_deletion_request"),
    )
    op.create_index("ix_participants_registered_by_user_id", "participants", ["registered_by_user_id"])
    op.create_index("ix_participants_created_at", "participants", ["created_at"])

    op.add_column("sessions", sa.Column("owner_user_id", sa.String(64),
                                        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("sessions", sa.Column("participant_id", sa.String(36),
                                        sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_sessions_owner_user_id", "sessions", ["owner_user_id"])
    op.create_index("ix_sessions_participant_id", "sessions", ["participant_id"])
    op.execute("UPDATE sessions SET owner_user_id = (SELECT s.user_id FROM students AS s "
               "WHERE s.id = sessions.student_id) WHERE student_id IS NOT NULL")

    op.create_table(
        "commitment_acceptances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('commitment', 'child_notice')", name="ck_commitment_acceptances_kind"),
        sa.UniqueConstraint("user_id", "kind", "version", name="uq_commitment_acceptances_user_kind_version"),
    )
    op.create_index("ix_commitment_acceptances_user_id", "commitment_acceptances", ["user_id"])

    op.create_table(
        "access_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.String(64), nullable=True),
        sa.Column("actor_role", sa.String(32), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("result", sa.String(16), nullable=False),
        sa.CheckConstraint("result IN ('success', 'denied', 'failure')", name="ck_access_audit_result"),
    )
    op.create_index("ix_access_audit_occurred_at", "access_audit", ["occurred_at"])
    op.create_index("ix_access_audit_actor_user_id", "access_audit", ["actor_user_id"])
    op.create_index("ix_access_audit_action", "access_audit", ["action"])
    op.create_index("ix_access_audit_resource", "access_audit", ["resource_type", "resource_id"])

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
    op.create_index("ix_participant_deletion_records_executed_by_user_id", "participant_deletion_records",
                    ["executed_by_user_id"])
    op.create_index("ix_participant_deletion_records_requested_by_user_id", "participant_deletion_records",
                    ["requested_by_user_id"])


def downgrade() -> None:
    op.drop_table("participant_deletion_records")
    op.drop_table("access_audit")
    op.drop_table("commitment_acceptances")
    op.drop_index("ix_sessions_participant_id", "sessions")
    op.drop_index("ix_sessions_owner_user_id", "sessions")
    op.drop_column("sessions", "participant_id")
    op.drop_column("sessions", "owner_user_id")
    op.drop_table("participants")
    op.drop_constraint("uq_psychologist_assignments_student_id", "psychologist_assignments", type_="unique")
    op.drop_column("users", "password_reset_at")
    # Las cuentas de administrador (cargo de la Facultad) no existían antes: se
    # desactivan y conservan el papel de soporte técnico como "admin".
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
    op.execute("UPDATE users SET is_active = false WHERE role = 'admin'")
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'superadmin'")
    op.create_check_constraint("ck_users_role_valid", "users", "role IN ('student','psychologist','admin')")
