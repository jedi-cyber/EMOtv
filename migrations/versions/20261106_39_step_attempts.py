"""Intentos por paso: repetir un reconocimiento o un ejercicio (bloque 2b, parte 2).

- recognition_results.attempt y practice_results.attempt (1 por defecto: los
  resultados existentes son el primer intento).
- La restricción única pasa de (session_id, step_index) a (session_id,
  step_index, attempt).
- guided_runs.step_attempt: el intento del paso en curso (1 por defecto).

Las dos tablas no tienen claves foráneas que apunten a ellas, así que en SQLite
(pruebas) batch_alter_table puede recrearlas.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_39"
down_revision = "20261106_38"
branch_labels = None
depends_on = None

TABLES = ("recognition_results", "practice_results")


def upgrade_table(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
        batch.drop_constraint(f"uq_{table}_session_step", type_="unique")
        batch.create_unique_constraint(f"uq_{table}_session_step_attempt", ["session_id", "step_index", "attempt"])


def downgrade_table(table: str) -> None:
    # Sin repeticiones: al volver queda solo el primer intento de cada paso.
    op.execute(sa.text(f"DELETE FROM {table} WHERE attempt > 1"))
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(f"uq_{table}_session_step_attempt", type_="unique")
        batch.create_unique_constraint(f"uq_{table}_session_step", ["session_id", "step_index"])
        batch.drop_column("attempt")


def upgrade() -> None:
    for table in TABLES:
        upgrade_table(table)
    op.add_column("guided_runs", sa.Column("step_attempt", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("guided_runs", "step_attempt")
    for table in TABLES:
        downgrade_table(table)
