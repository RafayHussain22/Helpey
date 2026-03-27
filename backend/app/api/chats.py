import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.chat import Chat
from app.models.document import Document
from app.models.message import Message
from app.models.user import User
from app.services.answer import stream_answer, stream_chitchat, build_context
from app.services.classifier import classify_query
from app.services.embeddings import query_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chats", tags=["chats"])


class CreateChatRequest(BaseModel):
    title: str = "New Chat"


class SendMessageRequest(BaseModel):
    content: str


@router.post("")
async def create_chat(
    body: CreateChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = Chat(user_id=user.id, title=body.title)
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return {"id": chat.id, "title": chat.title, "created_at": chat.created_at.isoformat()}


@router.get("")
async def list_chats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == user.id)
        .order_by(Chat.created_at.desc())
    )
    chats = result.scalars().all()
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()}
        for c in chats
    ]


@router.get("/{chat_id}")
async def get_chat(
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat)
        .options(selectinload(Chat.messages))
        .where(Chat.id == chat_id, Chat.user_id == user.id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "created_at": m.created_at.isoformat(),
            }
            for m in chat.messages
        ],
    }


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    await db.delete(chat)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get a streamed AI response."""
    # Verify chat belongs to user
    result = await db.execute(
        select(Chat)
        .options(selectinload(Chat.messages))
        .where(Chat.id == chat_id, Chat.user_id == user.id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Save user message
    user_msg = Message(
        chat_id=chat_id,
        user_id=user.id,
        role="user",
        content=body.content,
    )
    db.add(user_msg)
    await db.commit()

    # Auto-title on first message
    if len(chat.messages) <= 1:
        chat.title = body.content[:80]
        await db.commit()

    # Build chat history for context
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in chat.messages
    ]

    # Classify the query
    classification = classify_query(body.content)

    # Retrieve relevant chunks if needed
    chunks = []
    sources = []
    document_names: dict[str, str] = {}

    if classification == "search":
        chunks = await query_chunks(db, user.id, user.email, body.content, n_results=5)

        if chunks:
            # Get document names for citations
            doc_ids = list({c["document_id"] for c in chunks})
            doc_result = await db.execute(
                select(Document.id, Document.filename).where(Document.id.in_(doc_ids))
            )
            document_names = dict(doc_result.all())

            sources = [
                {
                    "document_id": c["document_id"],
                    "filename": document_names.get(c["document_id"], "Unknown"),
                    "excerpt": c["text"][:200],
                }
                for c in chunks
            ]

    # Stream the response
    async def event_stream():
        full_response = []

        # Send sources first if any
        if sources:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        try:
            if classification == "search":
                gen = stream_answer(body.content, chunks, document_names, chat_history)
            else:
                gen = stream_chitchat(body.content, chat_history)

            # Run sync generator in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            it = iter(gen)
            while True:
                text_chunk = await loop.run_in_executor(None, next, it, None)
                if text_chunk is None:
                    break
                full_response.append(text_chunk)
                yield f"data: {json.dumps({'type': 'text', 'content': text_chunk})}\n\n"

        except Exception as e:
            logger.exception("Streaming error")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            return

        # Save assistant message
        try:
            assistant_content = "".join(full_response)
            assistant_msg = Message(
                chat_id=chat_id,
                user_id=user.id,
                role="assistant",
                content=assistant_content,
                sources=sources or None,
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)

            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id})}\n\n"
        except Exception as e:
            logger.exception("Failed to save assistant message")
            yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to save response'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{chat_id}/messages")
async def list_messages(
    chat_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Chat not found")

    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
