"""
One-off: rewrite stored profile picture URLs from /file/<id> to /api/files/<id>.

Uploaded files are served at /api/files/<id> since the move to FastAPI. Run once per database
(the one in MONGODB_URI) after deploying that backend. Safe to run more than once.

Usage:
    uv run python scripts/rewrite_picture_urls.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from pymongo.errors import ConfigurationError

from config import MONGODB_URI

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    client = MongoClient(MONGODB_URI)
    try:
        database = client.get_default_database()
    except ConfigurationError:
        database = client.get_database("QuantumAiEd")
    # /file/<id> is the Flask-era form; /api/file/<id> only existed in pre-release builds of the FastAPI backend
    result = database.users.update_many(
        {"picture": {"$regex": "^(/api)?/file/[0-9a-f]{24}$"}},
        [
            {
                "$set": {
                    "picture": {
                        "$concat": ["/api/files/", {"$arrayElemAt": [{"$split": ["$picture", "/"]}, -1]}],
                    }
                }
            }
        ],
    )
    logger.info("Database %s: rewrote %d picture URLs", database.name, result.modified_count)
