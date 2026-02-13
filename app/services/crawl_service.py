"""
크롤링 서비스 로직
"""
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import structlog

from app.lib.commerce_playwright import search_items
from app.repositories.amazon_items import save_amazon_item
from app.services.keyword_service import get_customer_keywords

logger = structlog.get_logger()


def get_kst_now() -> datetime:
    """대한민국 서울 시간(KST, UTC+9)을 반환합니다."""
    return datetime.now(ZoneInfo("Asia/Seoul"))


def transform_category(category: Optional[str]) -> list[str]:
    """
    카테고리 문자열을 배열로 변환합니다.
    
    예: "피부미용 및 퍼스널 케어 > 메이크업" 
    -> ["피부미용 및 퍼스널 케어", "메이크업"]
    """
    if not category:
        return []
    
    return [cat.strip() for cat in category.split(" > ") if cat.strip()]


def transform_price(
    price: Optional[dict[str, Any]],
    original_price: Optional[dict[str, Any]],
    discount: Optional[str],
) -> dict[str, Any]:
    """
    가격 정보를 새로운 구조로 변환합니다.
    
    원본:
    - price: { "value": "35741", "currency": "KRW" }
    - originalPrice: { "value": "51144", "currency": "KRW" } 또는 null
    - discount: "25%" 또는 null
    
    변환:
    {
      "current": { "value": 35741.0, "currency": "KRW" },  # value는 Number 타입
      "original": { "value": 51144.0, "currency": "KRW" } 또는 null,  # value는 Number 타입
      "discount_rate": 30.0 또는 null (double 타입)
    }
    """
    # current price 변환 (value를 숫자로 변환)
    current_price = None
    if price:
        current_price = price.copy()
        if "value" in current_price:
            try:
                # 문자열인 경우 숫자로 변환
                if isinstance(current_price["value"], str):
                    current_price["value"] = float(current_price["value"])
                elif isinstance(current_price["value"], (int, float)):
                    current_price["value"] = float(current_price["value"])
            except (ValueError, TypeError):
                pass
    
    # original price 변환 (value를 숫자로 변환)
    original_price_converted = None
    if original_price:
        original_price_converted = original_price.copy()
        if "value" in original_price_converted:
            try:
                # 문자열인 경우 숫자로 변환
                if isinstance(original_price_converted["value"], str):
                    original_price_converted["value"] = float(original_price_converted["value"])
                elif isinstance(original_price_converted["value"], (int, float)):
                    original_price_converted["value"] = float(original_price_converted["value"])
            except (ValueError, TypeError):
                pass
    
    result: dict[str, Any] = {
        "current": current_price,
        "original": original_price_converted,
        "discount_rate": None,
    }
    
    # discount_rate 계산 (double 타입으로 저장)
    if discount:
        # "25%" 형식에서 숫자 추출
        try:
            discount_str = discount.replace("%", "").strip()
            result["discount_rate"] = float(discount_str)  # int가 아닌 float로 저장
        except (ValueError, TypeError):
            pass
    
    # discount가 없고 original_price와 price가 모두 있으면 계산
    if not result["discount_rate"] and original_price_converted and current_price:
        try:
            original_val = float(original_price_converted.get("value", 0))
            current_val = float(current_price.get("value", 0))
            if original_val > current_val and original_val > 0:
                discount_rate = ((original_val - current_val) / original_val) * 100
                result["discount_rate"] = float(discount_rate) if discount_rate > 0 else None
        except (ValueError, TypeError):
            pass
    
    return result


def transform_reviews(reviews: Optional[str]) -> Optional[int]:
    """
    리뷰 수 문자열을 정수로 변환합니다.
    
    예: "64" -> 64, "1,234" -> 1234
    """
    if not reviews:
        return None
    
    try:
        # 쉼표 제거 후 정수 변환
        reviews_clean = reviews.replace(",", "").strip()
        return int(reviews_clean)
    except (ValueError, TypeError):
        return None


def transform_amazon_item(item: dict[str, Any]) -> dict[str, Any]:
    """
    Amazon API 응답을 MongoDB 저장 형식으로 변환합니다.
    """
    # image 추출 (string 타입)
    image_url = None
    if item.get("image") and isinstance(item["image"], dict):
        image_url = item["image"].get("imageUrl")
    
    # 변환된 데이터 구조
    transformed = {
        "itemId": item.get("itemId"),  # 필수 필드
        "title": item.get("title"),  # 선택
        "price": transform_price(
            item.get("price"),
            item.get("originalPrice"),
            item.get("discount"),
        ),  # 선택 (object)
        "reviews": transform_reviews(item.get("reviews")),  # 선택
        "category": transform_category(item.get("category")),  # 선택 (array)
        "image": image_url,  # 선택 (string)
        "itemWebUrl": item.get("itemWebUrl"),  # 필수 필드
        "crawl_date": get_kst_now(),  # 선택 (date) - KST 기준
        "platform": "amazon",  # enum: ["amazon"]
    }
    
    return transformed


async def crawl_amazon_for_customer(
    customer_cd: int,
    price_level: int,
    limit: int = 5,
) -> dict[str, Any]:
    """
    고객 키워드를 조회하고 Amazon API를 호출하여 데이터를 수집하고 저장합니다.
    
    처리 순서:
    1. 고객 키워드 조회 (get_customer_keywords)
    2. 각 키워드로 Amazon 상품 검색 (search_items)
    3. 응답 데이터 가공 (transform_amazon_item)
       - category: " > " 기준 split하여 배열로 변환
       - price: current, original, discount_rate 구조로 변환
       - reviews: 문자열을 정수로 변환
    4. MongoDB 저장 (save_amazon_item)
    
    Returns:
        {
            "success": bool,
            "total_keywords": int,
            "total_items": int,
            "saved_items": int,
            "errors": list[str],
        }
    """
    # Step 1: 고객 키워드 조회
    # "/api/customer-keywords?customer_cd={customer_cd}&price_level={price_level}" 대신
    # 직접 함수 호출
    try:
        keywords_list = await get_customer_keywords(
            customer_cd=customer_cd,
            price_level=price_level
        )
        
        if not keywords_list:
            return {
                "success": False,
                "error": f"No keywords found for customer_cd={customer_cd}, price_level={price_level}",
                "total_keywords": 0,
                "total_items": 0,
                "saved_items": 0,
                "errors": [],
            }
        
        # 첫 번째 고객의 keywords 추출 (customer_cd가 지정된 경우 1개만 반환)
        customer_keywords = keywords_list[0]
        keywords = customer_keywords.keywords
        
        if not keywords:
            return {
                "success": False,
                "error": f"No keywords in customer data",
                "total_keywords": 0,
                "total_items": 0,
                "saved_items": 0,
                "errors": [],
            }
        
        logger.info("Customer keywords retrieved", 
                   customer_cd=customer_cd, 
                   price_level=price_level,
                   keyword_count=len(keywords),
                   keywords=keywords)
        
    except Exception as e:
        logger.error("Failed to fetch customer keywords", error=str(e), exc_info=True)
        return {
            "success": False,
            "error": f"Failed to fetch customer keywords: {str(e)}",
            "total_keywords": 0,
            "total_items": 0,
            "saved_items": 0,
            "errors": [],
        }
    
    # Step 2: 각 keyword로 Amazon API 호출
    # "/api/amazon/item_summary/search?keyword={keyword}&limit=5" 대신
    # 직접 함수 호출
    total_items = 0
    saved_items = 0
    errors: list[str] = []
    
    for keyword in keywords:
        logger.info("Crawling Amazon for keyword", keyword=keyword)
        try:
            # Amazon API 직접 호출 (HTTP 대신 함수 호출)
            result = await search_items("amazon", keyword, limit=limit)
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                errors.append(f"Keyword '{keyword}': {error_msg}")
                logger.warning("Amazon API failed", keyword=keyword, error=error_msg)
                continue
            
            items = result.get("items", [])
            
            if not items:
                logger.debug("No items found for keyword", keyword=keyword)
                continue
            
            # price.value가 null인 항목 필터링
            filtered_items = []
            for item in items:
                price = item.get("price")
                # price가 존재하고 value가 null이 아닌 경우만 포함
                if price and price.get("value") is not None:
                    filtered_items.append(item)
                else:
                    logger.debug(
                        "Item filtered out (price.value is null)",
                        keyword=keyword,
                        item_id=item.get("itemId"),
                        title=item.get("title")
                    )
            
            if not filtered_items:
                logger.debug("No items with valid price found for keyword", keyword=keyword)
                continue
            
            # Step 3: 각 아이템 변환 및 저장
            for item in filtered_items:
                try:
                    # 데이터 가공
                    transformed_item = transform_amazon_item(item)
                    
                    # MongoDB 저장
                    saved = await save_amazon_item(
                        customer_cd=customer_cd,
                        price_level=price_level,
                        keyword=keyword,
                        item_data=transformed_item,
                    )
                    
                    total_items += 1
                    if saved:
                        saved_items += 1
                    
                except Exception as item_error:
                    logger.error(
                        "Failed to save item",
                        keyword=keyword,
                        item_id=item.get("itemId"),
                        error=str(item_error),
                        exc_info=True
                    )
                    errors.append(f"Keyword '{keyword}', Item '{item.get('itemId')}': {str(item_error)}")
            
        except Exception as e:
            error_msg = f"Error processing keyword '{keyword}': {str(e)}"
            errors.append(error_msg)
            logger.error("Error processing keyword", keyword=keyword, error=str(e), exc_info=True)
    
    return {
        "success": True,
        "total_keywords": len(keywords),
        "total_items": total_items,
        "saved_items": saved_items,
        "errors": errors,
    }


async def crawl_amazon_batch(
    customer_cds: list[int],
    price_level: int,
    limit: int = 5,
) -> dict[str, Any]:
    """
    여러 고객에 대해 배치 크롤링을 실행합니다.
    
    Args:
        customer_cds: 크롤링할 고객 코드 리스트
        price_level: 가격 레벨
    
    Returns:
        {
            "success": bool,
            "total_customers": int,
            "processed_customers": int,
            "total_keywords": int,
            "total_items": int,
            "saved_items": int,
            "customer_results": list[dict],
            "errors": list[str],
        }
    """
    total_customers = len(customer_cds)
    processed_customers = 0
    total_keywords = 0
    total_items = 0
    total_saved_items = 0
    customer_results: list[dict] = []
    errors: list[str] = []
    
    logger.info(
        "Starting batch crawl",
        total_customers=total_customers,
        price_level=price_level
    )
    
    for customer_cd in customer_cds:
        try:
            logger.info(
                "Processing customer",
                customer_cd=customer_cd,
                price_level=price_level,
                progress=f"{processed_customers + 1}/{total_customers}"
            )
            
            # 각 고객에 대해 크롤링 실행
            result = await crawl_amazon_for_customer(
                customer_cd=customer_cd,
                price_level=price_level,
                limit=limit,
            )
            
            if result.get("success"):
                processed_customers += 1
                total_keywords += result.get("total_keywords", 0)
                total_items += result.get("total_items", 0)
                total_saved_items += result.get("saved_items", 0)
                
                customer_results.append({
                    "customer_cd": customer_cd,
                    "success": True,
                    "total_keywords": result.get("total_keywords", 0),
                    "total_items": result.get("total_items", 0),
                    "saved_items": result.get("saved_items", 0),
                    "errors": result.get("errors", []),
                })
            else:
                error_msg = result.get("error", "Unknown error")
                errors.append(f"Customer {customer_cd}: {error_msg}")
                customer_results.append({
                    "customer_cd": customer_cd,
                    "success": False,
                    "error": error_msg,
                })
                
        except Exception as e:
            error_msg = f"Customer {customer_cd}: {str(e)}"
            errors.append(error_msg)
            logger.error(
                "Failed to crawl customer",
                customer_cd=customer_cd,
                error=str(e),
                exc_info=True
            )
            customer_results.append({
                "customer_cd": customer_cd,
                "success": False,
                "error": str(e),
            })
    
    logger.info(
        "Batch crawl completed",
        total_customers=total_customers,
        processed_customers=processed_customers,
        total_keywords=total_keywords,
        total_items=total_items,
        total_saved_items=total_saved_items,
    )
    
    return {
        "success": True,
        "total_customers": total_customers,
        "processed_customers": processed_customers,
        "total_keywords": total_keywords,
        "total_items": total_items,
        "saved_items": total_saved_items,
        "customer_results": customer_results,
        "errors": errors,
    }
