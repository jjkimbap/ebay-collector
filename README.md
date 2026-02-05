# 상품 검색 API

다양한 플랫폼의 상품 검색 API 서비스입니다.

## 📋 기능 개요

- **eBay 상품 검색**: eBay Browse API를 사용한 상품 검색
- **AliExpress 상품 검색**: AliExpress API를 사용한 상품 검색
- **Amazon 상품 검색**: Amazon Product Advertising API를 사용한 상품 검색

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│  API Routes                                                   │
│  ├── GET /api/ebay/item_summary/search    - eBay 검색        │
│  ├── GET /api/ali/item_summary/search     - AliExpress 검색  │
│  └── GET /api/amazon/item_summary/search  - Amazon 검색     │
├─────────────────────────────────────────────────────────────┤
│  Collectors                                                  │
│  ├── ebay_collect.py    - eBay API 호출                     │
│  ├── ali_collect.py     - AliExpress API 호출               │
│  └── amazon_collect.py - Amazon API 호출                    │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 시작하기

### 요구사항

- Python 3.11+
- eBay/AliExpress/Amazon Developer 계정 (API 사용 시)

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
# 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 설정

# 서버 시작
uvicorn app.main:app --reload

# 또는 Python으로 직접 실행
python -m app.main
```

## 📡 API 사용법

### eBay 상품 검색

```bash
curl "http://localhost:8000/api/ebay/item_summary/search?keyword=drone&limit=3"
```

### AliExpress 상품 검색

```bash
curl "http://localhost:8000/api/ali/item_summary/search?keyword=drone&limit=3"
```

### Amazon 상품 검색

```bash
curl "http://localhost:8000/api/amazon/item_summary/search?keyword=drone&limit=3"
```

### Swagger UI

브라우저에서 `http://localhost:8000/docs` 접속하여 모든 API를 테스트할 수 있습니다.

### 검색 응답 예시

```json
{
  "success": true,
  "total": 44823,
  "itemSummaries": [
    {
      "itemId": "387049030112",
      "title": "Drone 2026 4K HD Dual Camera WiFi FPV RC Foldable",
      "price": {
        "value": "99.99",
        "currency": "USD"
      },
      "condition": "NEW",
      "itemWebUrl": "https://www.ebay.com/itm/387049030112"
    }
  ],
  "error": null
}
```

## 🔧 설정

### 환경변수

`.env` 파일에 다음 설정을 추가하세요:

```env
# Application
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000

# eBay API
EBAY_API_URL=https://api.ebay.com/buy/browse/v1/item_summary/search
EBAY_MARKETPLACE_ID=EBAY_US
EBAY_ENDUSERCTX=affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>

# AliExpress API
ALI_API_URL=https://api.aliexpress.com/item/search
ALI_API_KEY=your_ali_api_key

# Amazon API
AMAZON_API_URL=https://webservices.amazon.com/paapi5/searchitems
AMAZON_ACCESS_KEY=your_amazon_access_key
AMAZON_SECRET_KEY=your_amazon_secret_key
AMAZON_ASSOCIATE_TAG=your_associate_tag
```

### API 키 발급

- **eBay**: [eBay Developer Program](https://developer.ebay.com/)에서 OAuth 토큰 발급
- **AliExpress**: [AliExpress API](https://developers.aliexpress.com/)에서 API 키 발급
- **Amazon**: [Amazon Product Advertising API](https://affiliate-program.amazon.com/gp/advertising/api/detail/main.html)에서 키 발급

## 📁 프로젝트 구조

```
ebay-price-collector/
├── app/
│   ├── api/
│   │   ├── ebay_collect.py     # eBay 검색 API
│   │   ├── ali_collect.py       # AliExpress 검색 API
│   │   └── amazon_collect.py    # Amazon 검색 API
│   ├── core/
│   │   └── config.py           # 설정 관리
│   └── main.py                 # FastAPI 앱
├── tests/                      # 테스트
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── token                       # eBay OAuth 토큰 파일
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
- [x] eBay
- [x] AliExpress
- [x] Amazon
- [ ] Walmart
- [ ] Coupang

### 기능 확장
- [ ] 응답 캐싱 (Redis)
- [ ] 에러 재시도 로직 개선
- [ ] API 응답 포맷 통일
- [ ] 상세 상품 정보 조회 API

## 📝 라이선스

MIT License
