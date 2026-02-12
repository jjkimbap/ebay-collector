"""
MongoDB client and collection helpers.
"""
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from app.core.config import get_settings

_client: Optional[AsyncIOMotorClient] = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Get a singleton MongoDB client."""
    global _client

    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(
            settings.mongo_uri,
            uuidRepresentation="standard",
            serverSelectionTimeoutMS=3000,
        )
    return _client


def get_mongo_db() -> AsyncIOMotorDatabase:
    """Get the configured MongoDB database."""
    settings = get_settings()
    return get_mongo_client()[settings.mongo_db]


def get_collection(collection_name: str):
    """Get a MongoDB collection by name."""
    return get_mongo_db()[collection_name]


async def check_mongo_connection() -> tuple[bool, Optional[str]]:
    """
    Check MongoDB connection health.
    
    Returns:
        tuple: (is_connected: bool, error_message: Optional[str])
    """
    try:
        client = get_mongo_client()
        # Ping the database to check connection
        await client.admin.command("ping")
        return True, None
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
