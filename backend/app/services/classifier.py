"""Query classification using Anthropic Claude — determines if a question needs RAG."""
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a query classifier. Given a user message, determine if it requires searching the user's documents to answer.

Respond with exactly one word:
- "search" — if the question asks about specific information, facts, data, or content that would be in the user's files
- "chitchat" — if it's a greeting, thanks, clarification, or general conversation that doesn't need document lookup

Examples:
"What were Q3 revenue numbers?" → search
"Hi there" → chitchat
"Summarize the project proposal" → search
"Thanks!" → chitchat
"What does the contract say about termination?" → search
"Can you explain that in simpler terms?" → chitchat
"""


def classify_query(query: str) -> str:
    """Returns 'search' or 'chitchat'."""
    if not settings.ANTHROPIC_API_KEY:
        return "search"

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": query}],
        )
        result = response.content[0].text.strip().lower()
        classification = "search" if "search" in result else "chitchat"
        logger.info("Query classified as '%s': %s", classification, query[:80])
        return classification
    except Exception as e:
        logger.warning("Classification failed, defaulting to search: %s", e)
        return "search"
