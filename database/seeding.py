"""Auto-seed MongoDB collections on startup if they are empty (fresh deployment)."""

import logging
from datetime import UTC, datetime

from data.default_dashboard_config import DEFAULT_DASHBOARD_CONFIG
from data.default_lessons import get_lesson_documents
from database.db import db

logger = logging.getLogger(__name__)


async def seed_if_empty() -> None:
    """Seed dashboard_config and lessons_v2 if they're empty. Idempotent."""
    if await db.dashboard_config.count_documents({}) == 0:
        await db.dashboard_config.insert_one({**DEFAULT_DASHBOARD_CONFIG, "updated_at": datetime.now(UTC)})
        logger.info("Seeded dashboard_config from default")
    if await db.lessons_v2.count_documents({}) == 0:
        docs = get_lesson_documents()
        await db.lessons_v2.insert_many(docs)
        logger.info("Seeded lessons_v2 with %d lessons", len(docs))
