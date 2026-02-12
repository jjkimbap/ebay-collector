"""
Service layer for customer keyword retrieval.
"""
from typing import Optional

from app.repositories.customer_keywords import (
    fetch_all_customer_keywords,
    fetch_customer_keywords,
)
from app.schemas.customer_keyword import CustomerKeyword


async def get_customer_keywords(
    customer_cd: Optional[int] = None,
    *,
    price_level: int = 2,
) -> list[CustomerKeyword]:
    """
    Get keywords for one customer or all customers.
    """
    if customer_cd is not None:
        result = await fetch_customer_keywords(customer_cd, price_level=price_level)
        return [result] if result else []
    return await fetch_all_customer_keywords(price_level=price_level)
