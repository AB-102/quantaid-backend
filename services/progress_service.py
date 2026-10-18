"""Quiz results and level unlocking."""

from datetime import UTC, datetime

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

# Passing a quiz unlocks the next course, up to this courseId.
MAX_COURSE_ID = 8


def compute_level_unlock(course_id: int, passed: bool) -> int | None:
    """Return the courseId that passing this quiz unlocks, or None if nothing unlocks."""
    if passed and course_id < MAX_COURSE_ID:
        return course_id + 1
    return None


async def record_quiz_result(
    db: AsyncDatabase, email: str, course_id: int, score: int | float, passed: bool
) -> list[int] | None:
    """Store a quiz attempt and unlock the next course on a pass.

    Returns the user's unlocked levels after the update, or None if the user doesn't exist.
    """
    now = datetime.now(UTC)
    update: dict = {
        "$set": {"lastActivityAt": now},
        "$push": {"completedQuizzes": {"courseId": course_id, "score": score, "passed": passed, "timestamp": now}},
    }
    next_level = compute_level_unlock(course_id, passed)
    if next_level is not None:
        update["$addToSet"] = {"unlockedLevels": next_level}
    user = await db.users.find_one_and_update(
        {"user_id": email},
        update,
        projection={"_id": 0, "unlockedLevels": 1},
        return_document=ReturnDocument.AFTER,
    )
    if user is None:
        return None
    return user.get("unlockedLevels", [0])
