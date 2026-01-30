# eBay Price Collector

해외 가격 비교 서비스를 위한 eBay 상품 가격 정보 수집 모듈입니다.

## 📋 기능 개요

- **URL 파싱**: eBay 상품 URL에서 itemId 자동 추출
- **가격 수집**: eBay Browse API (우선) + HTML 스크래핑 (폴백)
- **가격 정규화**: 통화 변환, 배송비 분리/합산
- **히스토리 저장**: 가격 변동 추적을 위한 시계열 데이터 저장
- **가격 알림**: 목표 가격 도달 시 알림 트리거

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│  API Routes                                                   │
│  ├── POST /api/v1/parse-url    - URL 파싱                    │
│  ├── POST /api/v1/collect      - 가격 수집                   │
│  ├── POST /api/v1/track        - 상품 추적 등록              │
│  └── GET  /api/v1/history/{store}/{item_id} - 가격 히스토리  │
├─────────────────────────────────────────────────────────────┤
│  Collectors (멀티 스토어 확장 가능)                          │
│  └── EbayCollector                                           │
│      ├── EbayApiClient  (eBay Browse API)                    │
│      ├── EbayScraper    (HTML Fallback)                      │
│      └── EbayUrlParser  (URL 파싱)                           │
├─────────────────────────────────────────────────────────────┤
│  Services                                                     │
│  ├── CurrencyService      - 통화 변환                        │
│  └── PriceHistoryService  - DB 저장/조회                     │
├─────────────────────────────────────────────────────────────┤
│  Database (PostgreSQL)                                        │
│  ├── tracked_items    - 추적 중인 상품                       │
│  ├── price_history    - 가격 히스토리                        │
│  └── price_alerts     - 가격 알림 설정                       │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 시작하기

### 요구사항

- Python 3.11+
- PostgreSQL 15+
- Redis (선택, 캐싱용)
- eBay Developer 계정 (API 사용 시)

### 설치

```bash
# 저장소 클론
git clone <repository-url>
cd ebay-price-collector

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 수정
```

### Docker로 실행

```bash
# 전체 스택 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f api

# API 문서 접속
open http://localhost:8000/docs
```

### 로컬 실행

```bash
# PostgreSQL 실행 (Docker)
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=price_collector \
  -p 5432:5432 \
  postgres:15-alpine

# 마이그레이션 실행
alembic upgrade head

# 서버 시작
uvicorn app.main:app --reload
```

## 📡 API 사용법

### URL 파싱

```bash
curl -X POST http://localhost:8000/api/v1/parse-url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.ebay.com/itm/256123456789"}'
```

### 개별 상품 가격 수집

```bash
curl -X POST http://localhost:8000/api/v1/collect \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.ebay.com/itm/256123456789"}'
```

### 🔍 브랜드/키워드 검색 (NEW!)

**기본 검색:**
```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "3ce"}'
```

**카테고리 + 가격 필터 검색:**
```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "3ce lipstick",
    "category": "makeup",
    "min_price": 5,
    "max_price": 30,
    "sort": "price",
    "limit": 100
  }'
```

**브랜드 검색 (간편 API):**
```bash
curl "http://localhost:8000/api/v1/search/brand/3ce?category=makeup&limit=50"
```

**대량 수집 (여러 페이지):**
```bash
curl -X POST "http://localhost:8000/api/v1/search/bulk?max_items=500" \
  -H "Content-Type: application/json" \
  -d '{"query": "3ce"}'
```

**지원 카테고리 조회:**
```bash
curl http://localhost:8000/api/v1/search/categories
```

검색 응답 예시:
```json
{
  "success": true,
  "query": "3ce",
  "total_count": 875,
  "items": [
    {
      "item_id": "387049030112",
      "title": "3CE MAKEUP FIXER MIST 100ml, Setting Sprays",
      "price": 15.99,
      "currency": "USD",
      "shipping_fee": 9.50,
      "total_price": 25.49,
      "condition": "new",
      "seller_name": "kbeautybloom",
      "item_url": "https://www.ebay.com/itm/387049030112"
    }
  ],
  "price_stats": {
    "min_price": 8.99,
    "max_price": 45.00,
    "avg_price": 18.50,
    "item_count": 50
  },
  "page": 1,
  "has_more": true
}
```

### 상품 추적 등록

```bash
curl -X POST http://localhost:8000/api/v1/track \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.ebay.com/itm/256123456789",
    "target_price": 800.00,
    "notification_email": "user@example.com"
  }'
```

### 가격 히스토리 조회

```bash
curl "http://localhost:8000/api/v1/history/ebay/256123456789?days=30"
```

응답:
```json
{
  "store": "ebay",
  "item_id": "256123456789",
  "title": "Apple iPhone 14 Pro 256GB",
  "current_price": {"price": 999.99, "shipping_fee": 12.00, "currency": "USD"},
  "lowest_price": {"price": 899.99, "shipping_fee": 12.00, "currency": "USD"},
  "highest_price": {"price": 1099.99, "shipping_fee": 12.00, "currency": "USD"},
  "average_price": 989.50,
  "price_change_24h": -10.00,
  "price_change_percentage_24h": -0.99,
  "history": [...],
  "total_records": 45
}
```

## 🔧 설정

### 환경변수

| 변수 | 설명 | 기본값 |
|-----|------|--------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 | - |
| `REDIS_URL` | Redis 연결 문자열 | - |
| `EBAY_APP_ID` | eBay API App ID | - |
| `EBAY_CERT_ID` | eBay API Cert ID | - |
| `EBAY_SANDBOX_MODE` | 샌드박스 모드 사용 | true |
| `DEFAULT_CURRENCY` | 정규화 기준 통화 | USD |
| `COLLECTION_INTERVAL_MINUTES` | 수집 주기 (분) | 60 |

### eBay API 설정

1. [eBay Developer Program](https://developer.ebay.com/) 가입
2. Application 생성
3. App ID, Cert ID 발급
4. `.env` 파일에 설정

**API 없이 사용**: API 키가 없어도 HTML 스크래핑으로 기본 기능 사용 가능

## 📁 프로젝트 구조

```
ebay-price-collector/
├── app/
│   ├── api/
│   │   └── routes.py           # API 엔드포인트
│   ├── collectors/
│   │   ├── base.py             # 베이스 인터페이스
│   │   └── ebay/
│   │       ├── api_client.py   # eBay API 클라이언트
│   │       ├── scraper.py      # HTML 스크래퍼
│   │       ├── url_parser.py   # URL 파서
│   │       └── collector.py    # 통합 수집기
│   ├── core/
│   │   ├── config.py           # 설정 관리
│   │   └── database.py         # DB 연결
│   ├── models/
│   │   ├── database.py         # SQLAlchemy 모델
│   │   └── schemas.py          # Pydantic 스키마
│   ├── services/
│   │   ├── currency.py         # 통화 변환
│   │   └── price_history.py    # 가격 히스토리
│   └── main.py                 # FastAPI 앱
├── alembic/                    # DB 마이그레이션
├── tests/                      # 테스트
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 🧪 테스트

```bash
# 전체 테스트
pytest

# 커버리지 포함
pytest --cov=app

# 특정 테스트
pytest tests/test_url_parser.py -v
```

## 🔜 향후 확장 계획

### 지원 예정 스토어
- [ ] Amazon
- [ ] Walmart
- [ ] AliExpress
- [ ] Coupang

### 기능 확장
- [ ] 스케줄러 기반 자동 수집 (Celery/APScheduler)
- [ ] Redis 캐싱
- [ ] 이메일/푸시 알림
- [ ] 가격 예측 (Prophet)
- [ ] 관리자 대시보드

## 📝 라이선스

MIT License
