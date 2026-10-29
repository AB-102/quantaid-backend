"""
Link every lesson's quiz questions to the content they review by block label instead of by position.

Quiz questions stored lessonContentIndices, positions among the lesson's non-image blocks, which any edit above a
linked block silently re-pointed. This labels the referenced blocks (block "id") and writes each question's
lessonBlockIds. It keeps lessonContentIndices, so an older frontend still works until it's deployed.
It is idempotent — questions that already have lessonBlockIds are skipped.

Run it once per environment (local, staging-public, staging-rice, production) with that environment's MONGODB_URI.

Usage:
    uv run python scripts/migrate_quiz_links.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError

from config import MONGODB_URI
from core.quiz_links import link_questions_by_block_id

logger = logging.getLogger(__name__)


def migrate(db: Database) -> None:
    total = 0
    for lesson in db.lessons_v2.find({}, {"courseId": 1, "blocks": 1, "quiz": 1}).sort("courseId", 1):
        blocks = lesson.get("blocks", [])
        quiz = lesson.get("quiz", [])
        linked = link_questions_by_block_id(blocks, quiz)
        if linked == 0:
            logger.info("  courseId=%s already linked, skipping", lesson["courseId"])
            continue
        db.lessons_v2.update_one({"_id": lesson["_id"]}, {"$set": {"blocks": blocks, "quiz": quiz}})
        logger.info("  courseId=%s -> linked %d questions", lesson["courseId"], linked)
        total += linked
    logger.info("Done: %d questions linked by block label", total)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    client = MongoClient(MONGODB_URI)
    try:
        database = client.get_default_database()
    except ConfigurationError:
        database = client.get_database("QuantumAiEd")
    logger.info("Linking quiz questions by block label in database %s...", database.name)
    migrate(database)
