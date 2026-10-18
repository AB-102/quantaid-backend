from gridfs import AsyncGridFS
from pymongo import AsyncMongoClient
from pymongo.errors import ConfigurationError

from config import MONGODB_URI

if not MONGODB_URI or not MONGODB_URI.strip():
    raise RuntimeError("MONGODB_URI is not configured; please set it in the configuration or environment.")

# The async client binds to the event loop that first uses it, so only use it from the app's event loop.
# tz_aware=True returns UTC datetimes with a timezone, so JSON dates end in "+00:00" and browsers parse them as UTC.
client = AsyncMongoClient(MONGODB_URI, tz_aware=True)
try:
    db = client.get_default_database()
except ConfigurationError:
    db = client.get_database("QuantumAiEd")
fs = AsyncGridFS(db)
