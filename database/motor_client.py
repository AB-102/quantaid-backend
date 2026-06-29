from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError

from config import MONGODB_URI

motor_client = AsyncIOMotorClient(MONGODB_URI)
try:
    motor_db = motor_client.get_default_database()
except ConfigurationError:
    motor_db = motor_client.get_database("QuantumAiEd")
