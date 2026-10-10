"""Conversaciones de Emi y contador de rechazos por categoría.

chat_messages.in_scope queda nulo mientras n8n no responde; esas preguntas
cuentan para los límites de uso pero no se envían como historial. El contador
de rechazos no guarda el texto de las preguntas.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_15"
down_revision = "20261009_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_conversations_user_last_message", "chat_conversations",
                    ["user_id", "last_message_at"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(36),
                  sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("in_scope", sa.Boolean(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_chat_messages_role_valid"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id", "id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    op.create_table(
        "chat_rejection_counts",
        sa.Column("category", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("count >= 0", name="ck_chat_rejection_counts_non_negative"),
    )


def downgrade() -> None:
    op.drop_table("chat_rejection_counts")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_conversations_user_last_message", table_name="chat_conversations")
    op.drop_table("chat_conversations")
