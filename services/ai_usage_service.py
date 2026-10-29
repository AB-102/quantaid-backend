"""
Daily counts of AI requests made with Quantaid's own key.

One document per user per UTC day: {user_id, day, count}. It holds no message content, and MongoDB deletes it
once it's older than USAGE_RETENTION.
"""

from datetime import UTC, datetime, timedelta

from pymongo import ASCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from config import AI_DAILY_LIMIT

# Long enough to look back over a month of usage when tuning AI_DAILY_LIMIT
USAGE_RETENTION = timedelta(days=35)


def _today() -> datetime:
    """Midnight UTC at the start of today."""
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


async def create_indexes(db: AsyncDatabase) -> None:
    # Unique, so two first-of-the-day requests at once can't create two documents
    await db.ai_usage.create_index([("user_id", ASCENDING), ("day", ASCENDING)], unique=True)
    await db.ai_usage.create_index("day", expireAfterSeconds=int(USAGE_RETENTION.total_seconds()))


async def reserve_request(db: AsyncDatabase, email: str) -> bool:
    """Count one request against today's limit. Returns False if the limit was already used up."""
    usage = await db.ai_usage.find_one_and_update(
        {"user_id": email, "day": _today()},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    assert usage is not None  # upsert with ReturnDocument.AFTER always returns the document
    return usage["count"] <= AI_DAILY_LIMIT


async def release_request(db: AsyncDatabase, email: str) -> None:
    """Give back a request whose provider call failed, so a failure doesn't use up the user's limit."""
    await db.ai_usage.update_one({"user_id": email, "day": _today()}, {"$inc": {"count": -1}})


async def get_usage(db: AsyncDatabase, email: str) -> dict:
    today = _today()
    usage = await db.ai_usage.find_one({"user_id": email, "day": today}, {"count": 1})
    # Requests refused at the limit still add to the count, so cap what's reported
    used = min(usage["count"] if usage else 0, AI_DAILY_LIMIT)
    return {"used": used, "limit": AI_DAILY_LIMIT, "resetsAt": today + timedelta(days=1)}
