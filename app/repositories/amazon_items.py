"""
MongoDB repository for Amazon item documents.
"""
from datetime import datetime
from typing import Any, Optional

from app.core.config import get_settings
from app.db.mongodb import get_collection


async def save_amazon_item(
    customer_cd: int,
    price_level: int,
    keyword: str,
    item_data: dict[str, Any],
) -> bool:
    """
    Amazon 상품 데이터를 MongoDB에 저장합니다.
    
    중복 방지를 위해 (customer_cd, item_id, platform) 조합으로 upsert합니다.
    _id는 자동 생성되며, unique index로 중복을 방지합니다.
    """
    settings = get_settings()
    collection = get_collection("amazonPrices")
    
    item_id = item_data.get("itemId")
    platform = item_data.get("platform", "amazon")
    item_web_url = item_data.get("itemWebUrl")
    
    # 필수 필드 검증
    if not item_id:
        raise ValueError("item_id is required")
    if customer_cd is None:
        raise ValueError("customer_cd is required")
    if not item_web_url:
        raise ValueError("item_web_url is required")
    
    # 저장할 문서 구조
    document = {
        "item_id": item_id,  # 필수
        "customer_cd": customer_cd,  # 필수 (int 또는 null 허용)
        "item_web_url": item_web_url,  # 필수
        "platform": platform,  # enum: ["amazon"]
        "title": item_data.get("title"),  # 선택
        "price": item_data.get("price"),  # 선택 (object)
        "reviews": item_data.get("reviews"),  # 선택
        "category": item_data.get("category"),  # 선택 (array)
        "image": item_data.get("image"),  # 선택 (string)
        "crawl_date": item_data.get("crawl_date", datetime.utcnow()),  # 선택 (date)
    }
    
    # Unique index: (customer_cd, item_id, platform)
    # MongoDB는 _id를 자동 생성하지만, 이 조합으로 중복을 방지합니다
    filter_query = {
        "customer_cd": customer_cd,
        "item_id": item_id,
        "platform": platform,
    }
    
    try:
        # Upsert: 존재하면 업데이트, 없으면 삽입
        # _id는 MongoDB가 자동으로 생성합니다 (ObjectId)
        await collection.update_one(
            filter_query,
            {"$set": document},
            upsert=True
        )
        return True
    except Exception as e:
        # 중복 키 에러 등은 무시 (이미 존재하는 경우)
        return False
