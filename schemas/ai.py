from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

# Caps what one signed-in user can send to OpenAI per field (about 1,000 tokens); longer input gets a 422
MAX_TEXT_LENGTH = 4000

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_LENGTH)]
LimitedText = Annotated[str, StringConstraints(max_length=MAX_TEXT_LENGTH)]


class TextRequest(BaseModel):
    text: NonEmptyText


class ChatMessage(BaseModel):
    """
    One chat turn from the frontend. Only user/assistant roles are accepted, so a client
    can't inject a system prompt. Extra fields the frontend sends (like `type`) are dropped.
    """

    role: Literal["user", "assistant"]
    content: LimitedText


class ChatAboutTextRequest(BaseModel):
    highlightedText: LimitedText = ""
    messages: list[ChatMessage] = []
