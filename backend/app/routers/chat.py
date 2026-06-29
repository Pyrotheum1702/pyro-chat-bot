"""Streaming chat endpoint (Server-Sent Events).

Events on the stream:
  {"type":"start","conversation_id":N}
  {"type":"sources","sources":[{source,page,snippet}, ...]}
  {"type":"token","value":"..."}     (many)
  {"type":"error","message":"..."}   (on failure)
  {"type":"done"}
The full assistant answer is persisted once the stream completes.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .. import db, rag
from ..config import get_settings
from ..schemas import ChatRequest

router = APIRouter()
logger = logging.getLogger("ragchat")


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest):
    settings = get_settings()

    message = (req.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message must not be empty.")
    if len(message) > settings.max_message_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Message exceeds the {settings.max_message_chars}-character limit.",
        )

    conversation_id = req.conversation_id
    if conversation_id is None:
        title = (message[:60] + "…") if len(message) > 60 else message
        conversation_id = db.create_conversation(title or "New chat")

    # History = prior turns (fetch before recording the new user message).
    history = db.get_messages(conversation_id)
    db.add_message(conversation_id, "user", message)

    async def event_stream():
        yield _sse({"type": "start", "conversation_id": conversation_id})
        parts: list[str] = []
        try:
            async for event in rag.astream_answer(message, history):
                if event.get("type") == "token":
                    parts.append(event["value"])
                yield _sse(event)
        except Exception:
            # Log the detail server-side; send a generic message to the client.
            logger.exception("chat generation failed")
            yield _sse({"type": "error", "message": "Generation failed. Please try again."})

        answer = "".join(parts).strip()
        if answer:
            db.add_message(conversation_id, "assistant", answer)
        yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
