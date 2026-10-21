import logging
from typing import cast

import openai
from fastapi import APIRouter, HTTPException, status
from openai.types.chat import ChatCompletionMessageParam

from config import OPENAI_API_KEY
from database.db import db
from dependencies.auth import CurrentUser
from schemas.ai import ChatAboutTextRequest, TextRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI"])

openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-3.5-turbo"

# The frontend sends the whole conversation; only the latest messages go to OpenAI, so each request's size stays bounded
MAX_CHAT_HISTORY = 10


async def _personalization_context(email: str) -> str:
    """
    A note about the user's hobbies for the system prompt, or "" if
    the user turned hobby personalization off or has no hobbies.
    """
    user_doc = await db.users.find_one({"user_id": email}, {"_id": 0, "profile": 1, "hobby_personalization": 1})
    # Personalization defaults to on for new users
    if not user_doc or not user_doc.get("hobby_personalization", True):
        return ""
    hobbies = (user_doc.get("profile") or {}).get("favorite_hobbies", [])
    if not hobbies:
        return ""
    hobby_str = ", ".join(hobbies[:8])  # Cap at 8 to keep prompt short
    return (
        f"\nThe student's interests include: {hobby_str}. "
        "When possible, relate quantum concepts to these interests using analogies they'd find relatable. "
        "Don't force it — only use hobby-based analogies when they genuinely help explain the concept."
    )


async def _complete(messages: list[dict], max_tokens: int, temperature: float) -> str:
    """Run a chat completion. If OpenAI fails, log why and return a 502 without exposing the cause."""
    try:
        response = await openai_client.chat.completions.create(
            model=MODEL,
            messages=cast(list[ChatCompletionMessageParam], messages),
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except openai.APIError:
        logger.exception("OpenAI request failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI service unavailable") from None
    return (response.choices[0].message.content or "").strip()


@router.post("/explanations")
async def create_explanation(body: TextRequest, user: CurrentUser):
    personalization = await _personalization_context(user.email)
    system_prompt = {
        "role": "system",
        "content": (
            "You are an expert quantum computing tutor who excels at making complex concepts accessible. "
            "Your explanations should be:\n"
            "- Clear and detailed (200-300 words)\n"
            "- Use specific examples and analogies when helpful\n"
            "- Break down complex ideas into digestible steps\n"
            "- Use bullet points for key concepts\n"
            "- End by checking understanding or offering to clarify further\n"
            "- Be engaging and encouraging" + personalization
        ),
    }
    user_msg = {
        "role": "user",
        "content": (
            f"Please provide a detailed explanation of this quantum computing concept:\n\n"
            f'"{body.text}"\n\n'
            f"Structure your response (but without actually using number or bullet lists) as:\n"
            f"1. A brief overview of what this concept is\n"
            f"2. Key points broken down with bullet points\n"
            f"3. A concrete example or analogy if applicable\n"
            f"4. Why this concept matters in quantum computing\n"
            f"5. Ask if anything needs clarification"
        ),
    }
    explanation = await _complete([system_prompt, user_msg], max_tokens=250, temperature=0.6)
    return {"explanation": explanation}


@router.post("/chat")
async def chat(body: ChatAboutTextRequest, user: CurrentUser):
    highlighted_text = body.highlightedText or "(No specific highlighted text, user wants a general chat.)"
    personalization = await _personalization_context(user.email)
    system_prompt = {
        "role": "system",
        "content": (
            "You are a concise quantum tutor. Use bullet points, ask if the student understands, "
            "and provide an extra example at the end." + personalization
        ),
    }
    user_msg = {"role": "user", "content": f"Discuss the highlighted text: '{highlighted_text}'."}
    history = [message.model_dump() for message in body.messages[-MAX_CHAT_HISTORY:]]
    reply = await _complete([system_prompt, user_msg, *history], max_tokens=300, temperature=0.6)
    return {"assistantReply": reply}


@router.post("/analogies")
async def create_analogy(body: TextRequest, user: CurrentUser):
    personalization = await _personalization_context(user.email)
    system_prompt = {
        "role": "system",
        "content": (
            "Create clear, relatable analogies for quantum computing concepts using everyday objects. "
            "Keep responses 200-250 words. Use simple language and direct comparisons. "
            "Structure: introduce analogy, explain the parallel, connect back to quantum concept." + personalization
        ),
    }
    user_prompt = {
        "role": "user",
        "content": (
            f"Create a clear analogy for this quantum concept using an everyday scenario:\n\n"
            f'"{body.text}"\n\n'
            f"Use simple language and explain how the analogy relates to the quantum concept. "
            f"Keep it engaging but concise."
        ),
    }
    analogy = await _complete([system_prompt, user_prompt], max_tokens=250, temperature=0.7)
    return {"analogy": analogy}
