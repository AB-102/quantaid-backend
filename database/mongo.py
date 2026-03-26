from pymongo.mongo_client import MongoClient
from gridfs import GridFS
from config import MONGODB_URI

if not MONGODB_URI or not MONGODB_URI.strip():
    raise RuntimeError(
        "MONGODB_URI is not configured; please set it in the configuration or environment."
    )
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client.get_database("QuantumAiEd")
fs = GridFS(db)
