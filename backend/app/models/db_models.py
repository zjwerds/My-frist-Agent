import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class ConversationDB(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String(200), nullable=False, default="新对话")
    project_path = Column(String(500), nullable=True, default=None, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    message_count = Column(Integer, default=0)

    messages = relationship("MessageDB", back_populates="conversation", cascade="all, delete-orphan")


class MessageDB(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=gen_id)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    tool_calls = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    conversation = relationship("ConversationDB", back_populates="messages")
