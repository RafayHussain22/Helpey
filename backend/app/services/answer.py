"""Answer synthesis using Gemini with streaming."""
import logging
from collections.abc import Generator

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from app.config import settings

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

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
    """Convert chat history to Gemini format."""
    history = []
    for msg in chat_history[-10:]:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})
    return history


def stream_answer(
    query: str,
    chunks: list[dict],
    document_names: dict[str, str],
    chat_history: list[dict],
) -> Generator[str, None, None]:
    """Stream an answer using Gemini. Yields text chunks."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-2.5-flash-lite",
        system_instruction=SYSTEM_PROMPT,
    )

    context = build_context(chunks, document_names)
    history = _build_history(chat_history)

    if context:
        user_content = f"""Here are relevant excerpts from the user's documents:

{context}

---

User question: {query}"""
    else:
        user_content = query

    chat = model.start_chat(history=history)
    response = chat.send_message(user_content, stream=True, safety_settings=SAFETY_SETTINGS)

    for chunk in response:
        try:
            if chunk.text:
                yield chunk.text
        except (ValueError, IndexError):
            continue


def stream_chitchat(
    query: str,
    chat_history: list[dict],
) -> Generator[str, None, None]:
    """Stream a chitchat response (no document context needed)."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-2.5-flash-lite",
        system_instruction=CHITCHAT_SYSTEM,
    )

    history = _build_history(chat_history)
    chat = model.start_chat(history=history)
    response = chat.send_message(query, stream=True, safety_settings=SAFETY_SETTINGS)

    for chunk in response:
        try:
            if chunk.text:
                yield chunk.text
        except (ValueError, IndexError):
            continue
