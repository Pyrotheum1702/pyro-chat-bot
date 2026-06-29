"""Conversation list / create / detail endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import db
from ..schemas import NewConversation

router = APIRouter()


@router.get("/conversations")
def list_conversations():
    return db.list_conversations()


@router.post("/conversations")
def create_conversation(body: NewConversation):
    cid = db.create_conversation(body.title or "New chat")
    return db.get_conversation(cid)


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int):
    conv = db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"conversation": conv, "messages": db.get_messages(conversation_id)}
