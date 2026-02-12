"""
MongoDB repository for customer keyword documents.
"""
from typing import Optional

from app.core.config import get_settings
from app.db.mongodb import get_collection
from app.schemas.customer_keyword import CustomerKeyword


async def fetch_customer_keywords(
    customer_cd: int,
    *,
    price_level: int = 2,
) -> Optional[CustomerKeyword]:
    """Fetch keywords for a single customer by price level."""
    settings = get_settings()
    collection = get_collection(settings.mongo_keywords_collection)

    query = {"customer_cd": customer_cd, "service.price_level": price_level}

    doc = await collection.find_one(
        query,
        projection={
            "_id": 0,
            "customer_cd": 1,
            "customer_name": 1,
            "crawling.keywords": 1,
        },
    )
    if not doc:
        return None
    payload = {
        "customer_cd": doc.get("customer_cd"),
        "customer_name": doc.get("customer_name"),
        "keywords": doc.get("crawling", {}).get("keywords", []),
    }
    return CustomerKeyword(**payload)


async def fetch_all_customer_keywords(
    *,
    price_level: int = 2,
) -> list[CustomerKeyword]:
    """Fetch keywords for all customers by price level."""
    settings = get_settings()
    collection = get_collection(settings.mongo_keywords_collection)

    query = {"service.price_level": price_level}
    cursor = collection.find(
        query,
        projection={
            "_id": 0,
            "customer_cd": 1,
            "customer_name": 1,
            "crawling.keywords": 1,
        },
    )

    results: list[CustomerKeyword] = []
    async for doc in cursor:
        payload = {
            "customer_cd": doc.get("customer_cd"),
            "customer_name": doc.get("customer_name"),
            "keywords": doc.get("crawling", {}).get("keywords", []),
        }
        results.append(CustomerKeyword(**payload))
    return results
