from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TextRequest(BaseModel):
    text: NonEmptyText


class ChatMessage(BaseModel):
    """
    One chat turn from the frontend. Only user/assistant roles are accepted, so a client
    can't inject a system prompt. Extra fields the frontend sends (like `type`) are dropped.
    """

    role: Literal["user", "assistant"]
    content: str


class ChatAboutTextRequest(BaseModel):
    highlightedText: str = ""
    messages: list[ChatMessage] = []
