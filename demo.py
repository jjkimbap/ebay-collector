"""
eBay 가격 수집 테스트 스크립트

실제 eBay URL을 사용하여 데이터 수집 흐름을 테스트합니다.
"""
import asyncio
import json
from decimal import Decimal

# 실제 eBay 페이지에서 추출된 예시 데이터 (2024년 기준)
SAMPLE_EBAY_PAGE_DATA = {
    "url": "https://www.ebay.com/itm/356227859677",
    "extracted_data": {
        "item_id": "356227859677",
        "title": "Apple iPhone 15 Pro Max A2849 256GB Unlocked Very Good",
        "price": {
            "amount": 636.58,
            "currency": "USD",
            "list_price": 1299.99,
            "discount_percentage": 51
        },
        "shipping": {
            "cost": 0.00,
            "free": True,
            "method": "Free 2-3 day delivery"
        },
        "condition": "Very Good - Refurbished",
        "seller": {
            "id": "directauth",
            "name": "DirectAuth",
            "feedback_percentage": 98.9,
            "items_sold": "499K"
        },
        "item_specifics": {
            "Screen Size": "6.7 in",
            "Lock Status": "Network Unlocked",
            "Storage Capacity": "256 GB",
            "Brand": "Apple",
            "Model": "Apple iPhone 15 Pro Max"
        },
        "image_url": "https://i.ebayimg.com/images/g/7uMAAeSwlfxpJIvp/s-l1600.png"
    }
}


def demonstrate_url_parsing():
    """URL 파싱 데모"""
    print("=" * 60)
    print("1. URL 파싱 (URL Parsing)")
    print("=" * 60)
    
    from app.collectors.ebay.url_parser import EbayUrlParser
    
    test_urls = [
        "https://www.ebay.com/itm/356227859677",
        "https://www.ebay.com/itm/Apple-iPhone-15-Pro-Max/356227859677?hash=item123",
        "https://ebay.co.uk/itm/123456789012",
    ]
    
    for url in test_urls:
        result = EbayUrlParser.parse(url)
        print(f"\nInput URL: {url}")
        print(f"  Success: {result.success}")
        print(f"  Item ID: {result.item_id}")
        print(f"  Store: {result.store}")
        print(f"  Canonical URL: {result.canonical_url}")


def demonstrate_data_structure():
    """수집된 데이터 구조 데모"""
    print("\n" + "=" * 60)
    print("2. 수집 데이터 구조 (Collected Data Structure)")
    print("=" * 60)
    
    data = SAMPLE_EBAY_PAGE_DATA["extracted_data"]
    
    # 요구사항 문서에 명시된 형식으로 출력
    output = {
        "itemId": data["item_id"],
        "price": data["price"]["amount"],
        "shippingFee": data["shipping"]["cost"],
        "currency": data["price"]["currency"],
        "totalPrice": data["price"]["amount"] + data["shipping"]["cost"]
    }
    
    print("\n📦 기본 가격 데이터 (요구사항 문서 형식):")
    print(json.dumps(output, indent=2))
    
    # 확장된 정규화 데이터
    normalized = {
        "normalizedPrice": data["price"]["amount"],
        "currency": "USD",
        "includesShipping": data["shipping"]["free"],
        "includesTax": False
    }
    
    print("\n📊 정규화된 가격 데이터:")
    print(json.dumps(normalized, indent=2))


def demonstrate_api_response():
    """API 응답 형식 데모"""
    print("\n" + "=" * 60)
    print("3. API 응답 예시 (API Response Example)")
    print("=" * 60)
    
    data = SAMPLE_EBAY_PAGE_DATA["extracted_data"]
    
    # POST /api/v1/collect 응답 예시
    api_response = {
        "success": True,
        "data": {
            "store": "ebay",
            "item_id": data["item_id"],
            "metadata": {
                "title": data["title"],
                "seller_id": data["seller"]["id"],
                "seller_name": data["seller"]["name"],
                "condition": "refurbished",
                "listing_type": "buy_it_now",
                "image_url": data["image_url"]
            },
            "price_data": {
                "price": data["price"]["amount"],
                "shipping_fee": data["shipping"]["cost"],
                "currency": data["price"]["currency"],
                "total_price": data["price"]["amount"] + data["shipping"]["cost"]
            },
            "normalized_price": {
                "normalized_price": data["price"]["amount"],
                "normalized_total": data["price"]["amount"],
                "currency": "USD",
                "includes_shipping": True,
                "includes_tax": False
            },
            "collected_at": "2024-01-30T12:00:00Z",
            "collection_method": "scraping"
        },
        "cached": False,
        "error": None
    }
    
    print("\nPOST /api/v1/collect 응답:")
    print(json.dumps(api_response, indent=2, default=str))


def demonstrate_price_history_schema():
    """가격 히스토리 DB 스키마 데모"""
    print("\n" + "=" * 60)
    print("4. 가격 히스토리 DB 스키마 (Price History Schema)")
    print("=" * 60)
    
    db_record = {
        "id": 1,
        "store": "ebay",
        "item_id": "356227859677",
        "price": 636.58,
        "shipping_fee": 0.00,
        "currency": "USD",
        "normalized_price": 636.58,
        "normalized_total": 636.58,
        "normalized_currency": "USD",
        "includes_shipping": True,
        "includes_tax": False,
        "is_sale_price": True,
        "original_price": 1299.99,
        "bid_count": None,
        "auction_end_time": None,
        "collected_at": "2024-01-30T12:00:00Z",
        "collection_method": "scraping"
    }
    
    print("\nprice_history 테이블 레코드:")
    print(json.dumps(db_record, indent=2))


def demonstrate_collection_flow():
    """전체 수집 흐름 데모"""
    print("\n" + "=" * 60)
    print("5. 전체 수집 흐름 (Collection Flow)")
    print("=" * 60)
    
    flow = """
    사용자 요청: POST /api/v1/collect
    {"url": "https://www.ebay.com/itm/356227859677"}
    
    ┌─────────────────────────────────────────────────────────┐
    │ 1. URL 파싱 (EbayUrlParser)                            │
    │    - 도메인 검증: ebay.com ✓                           │
    │    - Item ID 추출: 356227859677                        │
    │    - Canonical URL 생성                                │
    └─────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 2. 가격 수집 (EbayCollector)                           │
    │    ┌─────────────────┐    ┌─────────────────┐         │
    │    │ eBay Browse API │ OR │ HTML Scraping   │         │
    │    │ (1순위)         │    │ (Fallback)      │         │
    │    └─────────────────┘    └─────────────────┘         │
    │                                                        │
    │    추출 데이터:                                        │
    │    - 상품명: Apple iPhone 15 Pro Max...               │
    │    - 가격: $636.58                                     │
    │    - 배송비: Free                                      │
    │    - 상태: Very Good - Refurbished                    │
    │    - 판매자: DirectAuth (98.9%)                       │
    └─────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 3. 가격 정규화 (CurrencyService)                       │
    │    - 통화 변환: USD → USD (변환 불필요)                │
    │    - 배송비 분리: $0.00 (무료 배송)                    │
    │    - 총액 계산: $636.58                                │
    └─────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 4. DB 저장 (PriceHistoryService)                       │
    │    - price_history 테이블에 레코드 추가                │
    │    - tracked_items 테이블 업데이트                     │
    │    - 알림 조건 체크 (price_alerts)                     │
    └─────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 5. 응답 반환                                           │
    │    {                                                   │
    │      "success": true,                                  │
    │      "data": { ... },                                  │
    │      "cached": false                                   │
    │    }                                                   │
    └─────────────────────────────────────────────────────────┘
    """
    print(flow)


if __name__ == "__main__":
    print("\n🛒 eBay 가격 수집 모듈 데모")
    print("=" * 60)
    
    demonstrate_url_parsing()
    demonstrate_data_structure()
    demonstrate_api_response()
    demonstrate_price_history_schema()
    demonstrate_collection_flow()
    
    print("\n" + "=" * 60)
    print("✅ 데모 완료")
    print("=" * 60)
    print("\n실제 서버 실행:")
    print("  docker-compose up -d")
    print("  curl -X POST http://localhost:8000/api/v1/collect \\")
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"url": "https://www.ebay.com/itm/356227859677"}\'')
