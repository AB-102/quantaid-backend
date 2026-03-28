"""Auto-seed MongoDB collections on startup if they are empty (fresh deployment)."""

import logging
import os
import sys
from datetime import UTC, datetime


def seed_if_empty() -> None:
    """Seed dashboard_config and lessons_v2 if empty. Idempotent."""
    _seed_dashboard_config()
    _seed_lessons()


def _seed_dashboard_config() -> None:
    from data.default_dashboard_config import DEFAULT_DASHBOARD_CONFIG
    from database.mongo import db

    if db.dashboard_config.count_documents({}) > 0:
        return
    doc = {**DEFAULT_DASHBOARD_CONFIG, "updated_at": datetime.now(UTC)}
    db.dashboard_config.insert_one(doc)
    logging.info("Seeded dashboard_config from default")


def _seed_lessons() -> None:
    from database.mongo import db

    if db.lessons_v2.count_documents({}) > 0:
        return

    # Import from scripts/ — add repo root to path if needed
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from scripts.migrate_lessons_to_db import get_lesson_documents

    docs = get_lesson_documents()
    if docs:
        db.lessons_v2.insert_many(docs)
        logging.info("Seeded lessons_v2 with %d lessons", len(docs))
