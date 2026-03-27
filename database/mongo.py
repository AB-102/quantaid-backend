from gridfs import GridFS
from pymongo.mongo_client import MongoClient

from config import MONGODB_URI

if not MONGODB_URI or not MONGODB_URI.strip():
    raise RuntimeError("MONGODB_URI is not configured; please set it in the configuration or environment.")
from pymongo.errors import ConfigurationError

mongo_client = MongoClient(MONGODB_URI)
try:
    db = mongo_client.get_default_database()
except ConfigurationError:
    db = mongo_client.get_database("QuantumAiEd")
fs = GridFS(db)
