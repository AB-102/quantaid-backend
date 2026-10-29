"""
The AI provider layer: which provider, model and key a request uses, and the call to it.

Routes build the prompts and call `complete()`; only this module talks to a provider. For now every request uses
Quantaid's own OpenAI key. User-supplied keys and other providers plug in here (see AI_PROVIDERS_PLAN.md).
"""

import logging
from dataclasses import dataclass
from typing import cast

import openai
from openai.types.chat import ChatCompletionMessageParam

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "openai"
# Must accept max_tokens and temperature, which the AI routes send. Reasoning models (gpt-5.x) don't.
DEFAULT_MODEL = "gpt-4o-mini"

_quantaid_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)


@dataclass(frozen=True)
class LLMChoice:
    """Which provider and model one AI request uses."""

    provider: str
    model: str
    # Quantaid's own key and wallet, so the request counts against the user's daily limit
    uses_quantaid_key: bool


class AIProviderError(Exception):
    """The provider call failed. The cause is logged here, never shown to the user."""


def default_llm() -> LLMChoice:
    return LLMChoice(provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL, uses_quantaid_key=True)


async def complete(llm: LLMChoice, messages: list[dict], max_tokens: int, temperature: float) -> str:
    """Run a chat completion and return the reply text."""
    try:
        response = await _quantaid_client.chat.completions.create(
            model=llm.model,
            messages=cast(list[ChatCompletionMessageParam], messages),
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except openai.APIError:
        logger.exception("OpenAI request failed")
        raise AIProviderError from None
    return (response.choices[0].message.content or "").strip()
