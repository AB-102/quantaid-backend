from pymongo.mongo_client import MongoClient
from gridfs import GridFS
from config import MONGODB_URI

if not MONGODB_URI or not MONGODB_URI.strip():
from pymongo.errors import ConfigurationError
from gridfs import GridFS
from config import MONGODB_URI

mongo_client = MongoClient(MONGODB_URI)
try:
    db = mongo_client.get_default_database()
except ConfigurationError:
    db = mongo_client.get_database("QuantumAiEd")
fs = GridFS(db)
