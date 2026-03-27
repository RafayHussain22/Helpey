"""Answer synthesis using Anthropic Claude with streaming."""
import logging
from collections.abc import Generator

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Helpey, an AI assistant that answers questions strictly based on the user's documents. You have access to relevant excerpts from the user's Google Drive files.

Rules:
- ONLY use information from the provided document excerpts to answer
- If the excerpts don't contain enough information to answer, say so clearly
- Cite which document the information comes from when possible
- Be concise and direct
- Never make up or hallucinate information not present in the excerpts
- If asked about something not in the documents, respond: "I couldn't find information about that in your documents."
"""

CHITCHAT_SYSTEM = """You are Helpey, a friendly AI assistant. You help users interact with their Google Drive documents. Keep responses brief and helpful. If the user asks a question that would require looking at their documents, suggest they ask it directly."""


def build_context(chunks: list[dict], document_names: dict[str, str]) -> str:
    """Build context string from retrieved chunks."""
    if not chunks:
        return ""

    parts = []
    for i, chunk in enumerate(chunks, 1):
        doc_name = document_names.get(chunk["document_id"], "Unknown document")
        parts.append(f'[Excerpt {i} — from "{doc_name}"]\n{chunk["text"]}')

    return "\n\n---\n\n".join(parts)


def _build_history(chat_history: list[dict]) -> list[dict]:
    """Convert chat history to Anthropic messages format."""
    messages = []
    for msg in chat_history[-10:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    return messages


def stream_answer(
    query: str,
    chunks: list[dict],
    document_names: dict[str, str],
    chat_history: list[dict],
) -> Generator[str, None, None]:
    """Stream an answer using Anthropic Claude. Yields text chunks."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    context = build_context(chunks, document_names)
    messages = _build_history(chat_history)

    if context:
        user_content = f"""Here are relevant excerpts from the user's documents:

{context}

---

User question: {query}"""
    else:
        user_content = query

    messages.append({"role": "user", "content": user_content})

    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def stream_chitchat(
    query: str,
    chat_history: list[dict],
) -> Generator[str, None, None]:
    """Stream a chitchat response (no document context needed)."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    messages = _build_history(chat_history)
    messages.append({"role": "user", "content": query})

    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=CHITCHAT_SYSTEM,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
