import os
from pymongo.mongo_client import MongoClient
from gridfs import GridFS
from config import MONGODB_URI

mongo_client = MongoClient(MONGODB_URI)
db = mongo_client.get_database(os.getenv("MONGODB_DB_NAME", "QuantumAiEd"))
fs = GridFS(db)
