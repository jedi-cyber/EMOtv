from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from emotv.application.ports.chat_repository import StoredChatMessage
from emotv.infrastructure.persistence.models import (
    ChatConversationRecord,
    ChatMessageRecord,
    ChatRejectionCountRecord,
)


class PostgresChatRepository:
    """Conversaciones de Emi. Cada consulta filtra por el usuario dueño."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def create_conversation(self, user_id: str, at: datetime) -> str:
        conversation_id = str(uuid4())
        with self._factory.begin() as db:
            db.add(ChatConversationRecord(id=conversation_id, user_id=user_id,
                                          created_at=at, last_message_at=at))
        return conversation_id

    def latest_conversation(self, user_id: str) -> str | None:
        with self._factory() as db:
            return db.scalar(
                select(ChatConversationRecord.id)
                .where(ChatConversationRecord.user_id == user_id)
                .order_by(ChatConversationRecord.last_message_at.desc(),
                          ChatConversationRecord.created_at.desc())
                .limit(1)
            )

    def owns(self, conversation_id: str, user_id: str) -> bool:
        with self._factory() as db:
            return db.scalar(select(func.count()).select_from(ChatConversationRecord).where(
                ChatConversationRecord.id == conversation_id,
                ChatConversationRecord.user_id == user_id,
            )) == 1

    def list_messages(self, conversation_id: str, limit: int) -> list[StoredChatMessage]:
        with self._factory() as db:
            rows = db.scalars(
                select(ChatMessageRecord)
                .where(ChatMessageRecord.conversation_id == conversation_id)
                .order_by(ChatMessageRecord.id.desc())
                .limit(limit)
            ).all()
        return [self._to_message(row) for row in reversed(rows)]

    def recent_in_scope(self, conversation_id: str, limit: int) -> list[StoredChatMessage]:
        if limit <= 0:
            return []
        with self._factory() as db:
            rows = db.scalars(
                select(ChatMessageRecord)
                .where(ChatMessageRecord.conversation_id == conversation_id,
                       ChatMessageRecord.in_scope.is_(True))
                .order_by(ChatMessageRecord.id.desc())
                .limit(limit)
            ).all()
        return [self._to_message(row) for row in reversed(rows)]

    def count_user_messages(self, user_id: str, since: datetime) -> int:
        with self._factory() as db:
            return int(db.scalar(
                select(func.count()).select_from(ChatMessageRecord)
                .join(ChatConversationRecord,
                      ChatConversationRecord.id == ChatMessageRecord.conversation_id)
                .where(ChatConversationRecord.user_id == user_id,
                       ChatMessageRecord.role == "user",
                       ChatMessageRecord.created_at >= since)
            ) or 0)

    def add_user_message(self, conversation_id: str, content: str, at: datetime) -> int:
        with self._factory.begin() as db:
            record = ChatMessageRecord(conversation_id=conversation_id, role="user",
                                       content=content, in_scope=None, category=None, created_at=at)
            db.add(record)
            db.execute(update(ChatConversationRecord)
                       .where(ChatConversationRecord.id == conversation_id)
                       .values(last_message_at=at))
            db.flush()
            return record.id

    def complete_exchange(self, user_message_id: int, conversation_id: str, answer: str,
                          in_scope: bool, category: str, at: datetime) -> None:
        with self._factory.begin() as db:
            db.execute(update(ChatMessageRecord)
                       .where(ChatMessageRecord.id == user_message_id)
                       .values(in_scope=in_scope, category=category))
            db.add(ChatMessageRecord(conversation_id=conversation_id, role="assistant",
                                     content=answer, in_scope=in_scope, category=category,
                                     created_at=at))
            db.execute(update(ChatConversationRecord)
                       .where(ChatConversationRecord.id == conversation_id)
                       .values(last_message_at=at))
            if not in_scope:
                self._increment(db, category, at)

    def record_rejection(self, category: str, at: datetime) -> None:
        with self._factory.begin() as db:
            self._increment(db, category, at)

    def rejection_counts(self) -> dict[str, int]:
        with self._factory() as db:
            return {row.category: row.count for row in db.scalars(select(ChatRejectionCountRecord))}

    def purge(self, before: datetime, include_conversations: bool = True) -> int:
        """Borra mensajes anteriores a ``before``.

        Con ``include_conversations`` también borra las conversaciones vacías
        e inactivas desde ``before``; al escribir no se borran, para no quitar
        la conversación en la que el usuario está preguntando.
        """
        with self._factory.begin() as db:
            removed = db.execute(delete(ChatMessageRecord).where(ChatMessageRecord.created_at < before)).rowcount
            if include_conversations:
                has_messages = select(ChatMessageRecord.id).where(
                    ChatMessageRecord.conversation_id == ChatConversationRecord.id).exists()
                db.execute(delete(ChatConversationRecord).where(
                    ChatConversationRecord.last_message_at < before, ~has_messages))
            return int(removed or 0)

    @staticmethod
    def _increment(db: Session, category: str, at: datetime) -> None:
        record = db.get(ChatRejectionCountRecord, category)
        if record is None:
            db.add(ChatRejectionCountRecord(category=category, count=1, last_at=at))
        else:
            record.count += 1
            record.last_at = at

    @staticmethod
    def _to_message(row: ChatMessageRecord) -> StoredChatMessage:
        return StoredChatMessage(role=row.role, content=row.content, in_scope=row.in_scope,
                                 category=row.category, created_at=row.created_at)
