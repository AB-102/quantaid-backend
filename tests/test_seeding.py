"""Startup seeding when several hosts start against the same empty database."""

import asyncio
import os

from pymongo import AsyncMongoClient

from data.default_lessons import get_lesson_documents
from database.seeding import seed_if_empty


def test_concurrent_seeding_inserts_each_document_once():
    async def seed_twice_at_once():
        # Its own client and event loop: the app's async client is bound to the TestClient's loop.
        # A throwaway database next to the test one, which the app has already seeded.
        client = AsyncMongoClient(os.environ["MONGODB_URI"], tz_aware=True)
        db = client.get_database(f"{client.get_default_database().name}-seeding")
        try:
            await asyncio.gather(seed_if_empty(db), seed_if_empty(db))
            return await db.lessons_v2.count_documents({}), await db.dashboard_config.count_documents({})
        finally:
            await client.drop_database(db.name)
            await client.close()

    lessons, configs = asyncio.run(seed_twice_at_once())
    assert lessons == len(get_lesson_documents())
    assert configs == 1
