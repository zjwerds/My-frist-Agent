import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.db_models import ConversationDB, MessageDB


def create_conversation(db: Session, project_path: str | None = None) -> ConversationDB:
    conv = ConversationDB(id=uuid.uuid4().hex[:12], title="新对话", project_path=project_path)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_conversations(db: Session, project_path: str | None = None) -> list[ConversationDB]:
    q = db.query(ConversationDB)
    if project_path is not None:
        q = q.filter(ConversationDB.project_path == project_path)
    return q.order_by(ConversationDB.updated_at.desc()).all()


def get_conversation(db: Session, conv_id: str) -> ConversationDB | None:
    return db.query(ConversationDB).filter(ConversationDB.id == conv_id).first()


def get_messages(db: Session, conv_id: str) -> list[MessageDB]:
    return (
        db.query(MessageDB)
        .filter(MessageDB.conversation_id == conv_id)
        .order_by(MessageDB.created_at.asc(), MessageDB.id.asc())
        .all()
    )


def add_message(
    db: Session, conv_id: str, role: str, content: str | None = None, tool_calls: str | None = None
) -> MessageDB:
    msg = MessageDB(
        id=uuid.uuid4().hex[:12],
        conversation_id=conv_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
    )
    db.add(msg)

    conv = db.query(ConversationDB).filter(ConversationDB.id == conv_id).first()
    if conv:
        conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        # Count only user messages to track turn count (tool messages excluded)
        if role == "user" and content:
            if conv.message_count == 0:
                # First user message: set title from content
                conv.title = content[:50] + ("..." if len(content) > 50 else "")
            # Atomic increment to avoid race conditions
            db.query(ConversationDB).filter(ConversationDB.id == conv_id).update(
                {ConversationDB.message_count: ConversationDB.message_count + 1},
                synchronize_session=False,
            )
            # Refresh the ORM object to reflect the updated count
            db.refresh(conv)

    db.commit()
    db.refresh(msg)
    return msg


def edit_message(db: Session, msg_id: str, new_content: str) -> MessageDB | None:
    msg = db.query(MessageDB).filter(MessageDB.id == msg_id).first()
    if not msg:
        return None
    msg.content = new_content
    msg.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(msg)
    return msg


def delete_messages_after(db: Session, conv_id: str, msg_id: str) -> int:
    cutoff = db.query(MessageDB).filter(MessageDB.id == msg_id).first()
    if not cutoff:
        return 0
    count = (
        db.query(MessageDB)
        .filter(
            MessageDB.conversation_id == conv_id,
            MessageDB.created_at > cutoff.created_at,
        )
        .delete(synchronize_session=False)
    )
    # Update message_count from actual user messages remaining
    user_count = (
        db.query(func.count(MessageDB.id))
        .filter(MessageDB.conversation_id == conv_id, MessageDB.role == "user")
        .scalar()
    )
    db.query(ConversationDB).filter(ConversationDB.id == conv_id).update(
        {ConversationDB.message_count: user_count},
        synchronize_session=False,
    )
    db.commit()
    return count


def branch_conversation(db: Session, source_conv_id: str, from_msg_id: str) -> ConversationDB:
    source_conv = db.query(ConversationDB).filter(ConversationDB.id == source_conv_id).first()
    if not source_conv:
        raise ValueError("Source conversation not found")

    cutoff_msg = db.query(MessageDB).filter(MessageDB.id == from_msg_id).first()
    if not cutoff_msg:
        raise ValueError("Source message not found")

    # Create new conversation
    new_conv = ConversationDB(
        id=uuid.uuid4().hex[:12],
        title=f"分支: {source_conv.title}",
        project_path=source_conv.project_path,
    )
    db.add(new_conv)
    db.flush()

    # Copy messages up to and including the cutoff message
    source_msgs = (
        db.query(MessageDB)
        .filter(
            MessageDB.conversation_id == source_conv_id,
            MessageDB.created_at <= cutoff_msg.created_at,
        )
        .order_by(MessageDB.created_at.asc())
        .all()
    )

    for sm in source_msgs:
        new_msg = MessageDB(
            id=uuid.uuid4().hex[:12],
            conversation_id=new_conv.id,
            role=sm.role,
            content=sm.content,
            tool_calls=sm.tool_calls,
            created_at=sm.created_at,
        )
        db.add(new_msg)

    # Recalculate title from first user message
    first_user = (
        db.query(MessageDB)
        .filter(MessageDB.conversation_id == new_conv.id, MessageDB.role == "user")
        .order_by(MessageDB.created_at.asc())
        .first()
    )
    if first_user and first_user.content:
        new_conv.title = f"分支: {first_user.content[:50]}{'...' if len(first_user.content) > 50 else ''}"

    # Count user messages
    new_conv.message_count = (
        db.query(func.count(MessageDB.id))
        .filter(MessageDB.conversation_id == new_conv.id, MessageDB.role == "user")
        .scalar()
    )

    db.commit()
    db.refresh(new_conv)
    return new_conv


def delete_conversation(db: Session, conv_id: str) -> bool:
    conv = db.query(ConversationDB).filter(ConversationDB.id == conv_id).first()
    if not conv:
        return False
    # Hard delete — cascade removes messages
    db.delete(conv)
    db.commit()
    return True


def get_stats(db: Session) -> dict:
    conv_count = db.query(ConversationDB).count()
    msg_count = db.query(MessageDB).count()
    # Rough estimate: each message ~1KB
    estimated_kb = msg_count * 1
    return {
        "conversations": conv_count,
        "messages": msg_count,
        "estimated_size": f"{estimated_kb} KB" if estimated_kb < 1024 else f"{estimated_kb / 1024:.1f} MB",
    }
