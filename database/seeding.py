"""Auto-seed MongoDB collections on startup if they are empty (fresh deployment)."""

import logging
from datetime import UTC, datetime

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import BulkWriteError, DuplicateKeyError

from data.default_dashboard_config import DEFAULT_DASHBOARD_CONFIG
from data.default_lessons import get_lesson_documents

logger = logging.getLogger(__name__)

DUPLICATE_KEY = 11000


async def seed_if_empty(db: AsyncDatabase) -> None:
    """Seed dashboard_config and lessons_v2 if they're empty. Idempotent.

    Several hosts can start against the same empty database at once, and each sees an empty collection.
    A fixed _id and a unique courseId make the second host's inserts fail as duplicates, which is ignored.
    Only an empty collection is seeded, so a lesson an admin deleted never comes back.
    """
    await db.lessons_v2.create_index("courseId", unique=True)

    if await db.dashboard_config.count_documents({}) == 0:
        try:
            await db.dashboard_config.insert_one(
                {"_id": "default", **DEFAULT_DASHBOARD_CONFIG, "updated_at": datetime.now(UTC)}
            )
            logger.info("Seeded dashboard_config from default")
        except DuplicateKeyError:
            logger.info("dashboard_config was seeded by another instance")

    if await db.lessons_v2.count_documents({}) == 0:
        docs = get_lesson_documents()
        try:
            await db.lessons_v2.insert_many(docs, ordered=False)
            logger.info("Seeded lessons_v2 with %d lessons", len(docs))
        except BulkWriteError as e:
            if any(error["code"] != DUPLICATE_KEY for error in e.details["writeErrors"]):
                raise
            logger.info("lessons_v2 was seeded by another instance")
