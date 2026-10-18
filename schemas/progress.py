from pydantic import BaseModel


class SaveQuizResultRequest(BaseModel):
    courseId: int
    score: int | float
    passed: bool


class OnboardingUpdate(BaseModel):
    hasViewedFirstLesson: bool
