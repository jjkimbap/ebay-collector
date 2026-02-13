"""
MongoDB repository for Amazon item documents.
"""
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import structlog

from app.core.config import get_settings
from app.db.mongodb import get_collection

logger = structlog.get_logger()


def get_kst_now() -> datetime:
    """대한민국 서울 시간(KST, UTC+9)을 반환합니다."""
    return datetime.now(ZoneInfo("Asia/Seoul"))


async def save_amazon_item(
    customer_cd: int,
    price_level: int,
    keyword: str,
    item_data: dict[str, Any],
) -> bool:
    """
    Amazon 상품 데이터를 MongoDB에 저장합니다.
    
    항상 새로운 문서로 삽입하여 시간별 가격 추이를 추적할 수 있도록 합니다.
    같은 item_id가 여러 번 수집되어도 각각 별도의 문서로 저장됩니다.
    _id는 MongoDB가 자동으로 생성합니다 (ObjectId).
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
    
    # 저장할 데이터 구조 
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
        "crawl_date": item_data.get("crawl_date", get_kst_now()),  # 필수 - KST 기준
    }
    
    try:
        # 항상 새로운 문서로 삽입하여 시간별 가격 추이를 추적할 수 있도록 함
        # 같은 item_id가 여러 번 수집되어도 각각 별도의 문서로 저장됨
        # _id는 MongoDB가 자동으로 생성합니다 (ObjectId)
        await collection.insert_one(document)
        return True
    except Exception as e:
        logger.error("Failed to save amazon item", error=str(e), item_id=item_id, customer_cd=customer_cd)
        return False


async def create_indexes():
    """
    MongoDB 컬렉션에 TTL 인덱스를 생성합니다.
    
    생성되는 인덱스:
    - crawl_date - TTL 인덱스 (30일 후 자동 삭제)
    """
    collection = get_collection("amazonPrices")
    
    try:
        # TTL 인덱스: crawl_date 기준으로 30일 후 자동 삭제
        # MongoDB는 60초마다 TTL 인덱스를 확인하여 만료된 문서를 삭제합니다
        # expireAfterSeconds: 30일 = 30 * 24 * 60 * 60 = 2,592,000초
        await collection.create_index(
            [("crawl_date", 1)],
            expireAfterSeconds=2592000,  # 30일 (초 단위)
            name="idx_crawl_date_ttl"
        )
        logger.info("Created TTL index on crawl_date (30 days expiration)")
        
        return True
    except Exception as e:
        # 인덱스가 이미 존재하는 경우 등은 무시
        logger.warning("Failed to create TTL index (may already exist)", error=str(e))
        return False
