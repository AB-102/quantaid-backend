"""Quiz results."""

from datetime import UTC, datetime

from pymongo.asynchronous.database import AsyncDatabase


async def record_quiz_result(db: AsyncDatabase, email: str, course_id: int, score: int | float, passed: bool) -> bool:
    """Store a quiz attempt. Returns False if the user doesn't exist.

    Which lessons a student can open is worked out by the frontend from these attempts and the dashboard order.
    """
    now = datetime.now(UTC)
    result = await db.users.update_one(
        {"user_id": email},
        {
            "$set": {"lastActivityAt": now},
            "$push": {"completedQuizzes": {"courseId": course_id, "score": score, "passed": passed, "timestamp": now}},
        },
    )
    return result.matched_count == 1
