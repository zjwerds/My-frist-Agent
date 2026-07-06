import re
from fastapi import APIRouter, Depends, Query, Body, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud import history as crud
from app.crud.history import get_messages

router = APIRouter(prefix="/api/history")

ANALYSIS_PREFIX_RE = re.compile(r'^【前置分析】\n.*?\n---\n', re.DOTALL)


def _strip_analysis(content: str | None) -> str | None:
    """Remove the 【前置分析】...--- prefix added by assess_user_intent."""
    if content and content.startswith('【前置分析】'):
        return ANALYSIS_PREFIX_RE.sub('', content, count=1)
    return content


@router.get("")
def list_conversations(project_path: str | None = Query(None), db: Session = Depends(get_db)):
    convs = crud.get_conversations(db, project_path=project_path)
    return [
        {
            "id": c.id,
            "title": c.title,
            "project_path": c.project_path,
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            "message_count": c.message_count or 0,
        }
        for c in convs
    ]


@router.get("/{conv_id}")
def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = crud.get_conversation(db, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = get_messages(db, conv_id)
    return {
        "id": conv.id,
        "title": conv.title,
        "project_path": conv.project_path,
        "created_at": conv.created_at.isoformat() if conv.created_at else "",
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else "",
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": _strip_analysis(m.content) if m.role in ('user',) else m.content,
                "tool_calls": m.tool_calls,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in msgs
        ],
    }


@router.post("")
def create_conversation(body: dict | None = Body(None), db: Session = Depends(get_db)):
    project_path = body.get("project_path") if body else None
    conv = crud.create_conversation(db, project_path=project_path)
    return {
        "id": conv.id,
        "title": conv.title,
        "project_path": conv.project_path,
        "created_at": conv.created_at.isoformat() if conv.created_at else "",
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else "",
        "message_count": 0,
    }


@router.delete("/{conv_id}")
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    success = crud.delete_conversation(db, conv_id)
    return {"success": success}


@router.put("/{conv_id}")
def rename_conversation(conv_id: str, body: dict, db: Session = Depends(get_db)):
    conv = crud.get_conversation(db, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.title = body.get("title", conv.title)
    db.commit()
    return {"success": True}


@router.put("/{conv_id}/messages/{msg_id}")
def edit_message(conv_id: str, msg_id: str, body: dict = Body(...), db: Session = Depends(get_db)):
    msg = crud.edit_message(db, msg_id, body.get("content", ""))
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    deleted = crud.delete_messages_after(db, conv_id, msg_id)
    return {
        "message": {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "tool_calls": msg.tool_calls,
            "created_at": msg.created_at.isoformat() if msg.created_at else "",
            "updated_at": msg.updated_at.isoformat() if msg.updated_at else "",
        },
        "deleted_count": deleted,
    }


@router.post("/{conv_id}/branch")
def branch_conversation(conv_id: str, from_msg_id: str = Query(...), db: Session = Depends(get_db)):
    try:
        conv = crud.branch_conversation(db, conv_id, from_msg_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    msgs = get_messages(db, conv.id)
    return {
        "id": conv.id,
        "title": conv.title,
        "project_path": conv.project_path,
        "created_at": conv.created_at.isoformat() if conv.created_at else "",
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else "",
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": _strip_analysis(m.content) if m.role in ('user',) else m.content,
                "tool_calls": m.tool_calls,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in msgs
        ],
    }


@router.get("/stats/summary")
def get_stats(db: Session = Depends(get_db)):
    return crud.get_stats(db)
