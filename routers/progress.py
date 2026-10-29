import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from config import FIRST_TIME_USER_EMAIL
from database.db import db
from dependencies.auth import CurrentUser
from schemas.progress import OnboardingUpdate, SaveQuizResultRequest
from services.progress_service import record_quiz_result

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["Me"])


@router.get("/progress")
async def get_progress(user: CurrentUser):
    user_doc = await db.users.find_one(
        {"user_id": user.email},
        {"_id": 0, "completedQuizzes": 1, "hasViewedFirstLesson": 1, "name": 1, "picture": 1},
    )
    if user_doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    has_viewed_first_lesson = user_doc.get("hasViewedFirstLesson", False)
    if user.email == FIRST_TIME_USER_EMAIL:
        has_viewed_first_lesson = False  # the test user always sees onboarding
    return {
        "completedQuizzes": user_doc.get("completedQuizzes", []),
        "hasViewedFirstLesson": has_viewed_first_lesson,
        "email": user.email,
        "name": user_doc.get("name", ""),
        "picture": user_doc.get("picture", ""),
    }


@router.post("/quiz-results", status_code=status.HTTP_201_CREATED)
async def create_quiz_result(body: SaveQuizResultRequest, user: CurrentUser):
    """Record a quiz attempt."""
    if not await record_quiz_result(db, user.email, body.courseId, body.score, body.passed):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    logger.debug("Quiz result saved for %s, course %s, passed=%s", user.email, body.courseId, body.passed)
    return {"message": "Quiz result saved successfully"}


@router.put("/onboarding")
async def update_onboarding(body: OnboardingUpdate, user: CurrentUser):
    # The test user always goes through onboarding, so don't remember that they saw it
    if user.email == FIRST_TIME_USER_EMAIL:
        return {"message": "Test user - onboarding state not saved"}
    update: dict = {"hasViewedFirstLesson": body.hasViewedFirstLesson}
    if body.hasViewedFirstLesson:
        update["firstLessonViewedAt"] = datetime.now(UTC)
    await db.users.update_one({"user_id": user.email}, {"$set": update})
    return {"message": "Onboarding state saved"}
