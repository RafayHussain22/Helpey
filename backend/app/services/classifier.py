"""Query classification using Gemini — determines if a question needs RAG."""
import logging

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
    if not settings.GEMINI_API_KEY:
        return "search"

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            "gemini-2.5-flash-lite",
            system_instruction=SYSTEM_PROMPT,
        )
        response = model.generate_content(query, safety_settings=SAFETY_SETTINGS)
        if not response.candidates or not response.candidates[0].content.parts:
            logger.warning("Empty classifier response, defaulting to search")
            return "search"
        result = response.candidates[0].content.parts[0].text.strip().lower()
        classification = "search" if "search" in result else "chitchat"
        logger.info("Query classified as '%s': %s", classification, query[:80])
        return classification
    except Exception as e:
        logger.warning("Classification failed, defaulting to search: %s", e)
        return "search"
