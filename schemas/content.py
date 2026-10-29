from pydantic import BaseModel, Field

# Lesson blocks and quiz questions stay loosely typed on purpose: their stored shape isn't pinned down,
# and a strict model would silently drop unknown fields the next time an admin saves a lesson.


class LessonCreate(BaseModel):
    courseId: int
    title: str = Field(min_length=1)
    blocks: list[dict] = []
    quiz: list[dict] = []
    interactiveTerms: dict = {}


class LessonUpdate(BaseModel):
    """Partial update: only the fields present in the request change."""

    title: str | None = None
    blocks: list[dict] | None = None
    quiz: list[dict] | None = None
    interactiveTerms: dict | None = None


class DashboardConfigUpdate(BaseModel):
    sections: list[dict]
    courses: list[dict]
