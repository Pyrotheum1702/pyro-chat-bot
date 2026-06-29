"""Pydantic request/response models."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None


class NewConversation(BaseModel):
    title: Optional[str] = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: float


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: float


class DocumentOut(BaseModel):
    id: int
    filename: str
    chunks: int
    created_at: float


class Source(BaseModel):
    source: str
    page: Optional[int] = None
    snippet: str


class ConversationDetail(BaseModel):
    conversation: ConversationOut
    messages: List[MessageOut]
