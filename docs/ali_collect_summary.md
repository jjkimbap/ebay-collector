# AliExpress 상품 검색 API - 요약

## 빠른 참조

### 파일 구조
```
app/api/ali_collect.py          # API 엔드포인트
  └─> app/lib/commerce_playwright.py  # 크롤링 엔진
      └─> app/core/config.py          # 설정
```

### 핵심 라이브러리
- `fastapi`: API 프레임워크
- `playwright`: 브라우저 자동화
- `anyio`: 비동기-동기 브릿지
- `structlog`: 로깅

### API 사용법
```bash
GET /api/ali/item_summary/search?keyword=3ce&limit=10
```

### 주요 설정
- 타임아웃: 10분 (600,000ms)
- 브라우저: Chromium (headless 모드 지원)
- 프록시: 선택적 지원

### 크롤링 로직 위치
- 파일: `app/lib/commerce_playwright.py`
- 메서드: `EcommerceScraper.scrape_aliexpress()` (라인 250-305)

