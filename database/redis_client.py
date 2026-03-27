import logging

import redis as redis_lib

from config import REDIS_URL

logger = logging.getLogger(__name__)

# Redis client — None when REDIS_URL is not set (local dev without Docker).
# Modules that use Redis check `if redis_client:` and fall back to in-memory behavior.
redis_client = None

if REDIS_URL:
    try:
        redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info("Connected to Redis at %s", REDIS_URL)
    except redis_lib.ConnectionError:
        logger.warning("Redis unavailable at %s — falling back to in-memory", REDIS_URL)
        redis_client = None
