"""
Insert the default lessons (data/default_lessons.py) into the lessons_v2 collection.

The app seeds an empty lessons_v2 on startup; this script fills in default lessons that are
missing from a database that already has some. It is idempotent — it skips courseIds that already exist.

Usage:
    uv run python scripts/migrate_lessons_to_db.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError

from config import MONGODB_URI
from data.default_lessons import get_lesson_documents

logger = logging.getLogger(__name__)


def migrate(db: Database) -> None:
    inserted = 0
    skipped = 0
    for doc in get_lesson_documents():
        if db.lessons_v2.find_one({"courseId": doc["courseId"]}):
            logger.info("  courseId=%s already exists, skipping", doc["courseId"])
            skipped += 1
            continue
        db.lessons_v2.insert_one(doc)
        logger.info(
            '  courseId=%s "%s" -> %d blocks, %d quiz questions',
            doc["courseId"],
            doc["title"],
            len(doc["blocks"]),
            len(doc["quiz"]),
        )
        inserted += 1
    logger.info("Done: %d lessons inserted, %d skipped (already existed)", inserted, skipped)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    client = MongoClient(MONGODB_URI)
    try:
        database = client.get_default_database()
    except ConfigurationError:
        database = client.get_database("QuantumAiEd")
    logger.info("Migrating default lessons to the lessons_v2 collection of database %s...", database.name)
    migrate(database)
