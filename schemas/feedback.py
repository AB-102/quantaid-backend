from typing import Literal

from pydantic import BaseModel


class FeedbackStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
