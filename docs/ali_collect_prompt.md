# AliExpress 상품 검색 API 개발 프롬프트

## 요청 사항
AliExpress 상품 검색 API (`app/api/ali_collect.py`)와 관련된 파일 및 라이브러리를 정리하고, 해당 API 요청에 대한 개발 프롬프트를 작성해주세요.

## 현재 구조

### API 엔드포인트
- **경로**: `GET /api/ali/item_summary/search`
- **파라미터**:
  - `keyword` (필수): 검색 키워드
  - `limit` (선택, 기본값: 3): 결과 수 (1-200)

### 응답 형식
```json
{
  "success": true,
  "total": 10,
  "itemSummaries": [
    {
      "itemId": null,
      "title": "상품 제목",
      "price": {
        "value": "29.99",
        "currency": "USD"
      },
      "condition": null,
      "image": {
        "imageUrl": "https://..."
      },
      "itemWebUrl": "https://www.aliexpress.com/item/..."
    }
  ],
  "error": null
}
```

## 파일 의존성

### 직접 사용 파일
1. **app/api/ali_collect.py**
   - FastAPI 라우터 정의
   - 요청/응답 모델 정의
   - `app.lib.commerce_playwright.search_items()` 호출

2. **app/lib/commerce_playwright.py**
   - Playwright 기반 크롤링 엔진
   - `EcommerceScraper` 클래스
   - `scrape_aliexpress()` 메서드
   - `search_items()` 비동기 래퍼

3. **app/core/config.py**
   - 애플리케이션 설정 관리
   - Playwright 관련 설정 (headless, proxy, domain)

### 라이브러리 의존성

#### 필수
- `fastapi`: 웹 프레임워크
- `pydantic`: 데이터 검증
- `playwright`: 브라우저 자동화
- `anyio`: 비동기-동기 브릿지
- `structlog`: 구조화된 로깅

#### 선택적
- `playwright-stealth`: 봇 탐지 회피

#### 표준 라이브러리
- `typing`, `dataclasses`, `random`, `re`, `time`, `urllib.parse`

## 개발 가이드

### 1. 환경 설정
```bash
# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

# 환경 변수 설정 (.env)
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_PROXY=  # 선택적
```

### 2. API 테스트
```bash
# Swagger UI
http://localhost:8003/docs

# 직접 호출
curl "http://localhost:8003/api/ali/item_summary/search?keyword=3ce&limit=10"
```

### 3. 크롤링 로직 수정 시

#### AliExpress 크롤링 메서드 위치
- 파일: `app/lib/commerce_playwright.py`
- 메서드: `EcommerceScraper.scrape_aliexpress()`
- 라인: 250-305

#### 주요 수정 포인트
1. **URL 변경**: `page.goto()` 호출 부분
2. **Selector 변경**: `page.wait_for_selector()`, `page.query_selector_all()` 부분
3. **데이터 추출**: 각 필드 추출 로직 (제목, 가격, 이미지, 링크)
4. **타임아웃**: 현재 10분 (600000ms)으로 설정됨

### 4. 에러 처리
- 타임아웃: 10분 초과 시 `ScrapeResult(success=False, error="...")` 반환
- Selector 미발견: 경고 로그 후 계속 진행
- 네트워크 오류: 예외 캐치 후 에러 반환

### 5. 성능 최적화
- 브라우저 재사용 고려 (현재는 요청마다 새로 생성)
- 캐싱 전략 추가 가능
- 병렬 처리 고려 (여러 키워드 동시 검색)

### 6. 테스트
```python
# 단위 테스트 예시
async def test_ali_search():
    result = await search_items("aliexpress", "3ce", 10)
    assert result["success"] == True
    assert len(result["items"]) > 0
```

## 주의사항

1. **타임아웃**: 현재 10분으로 설정되어 있어 느린 네트워크에서도 작동
2. **봇 탐지**: Stealth 플러그인 사용으로 봇 탐지 회피 시도
3. **인간처럼 보이는 동작**: 1-2.8초 랜덤 지연으로 자연스러운 동작 모방
4. **User-Agent 랜덤화**: 여러 User-Agent 중 랜덤 선택
5. **프록시 지원**: 환경 변수로 프록시 설정 가능

## 향후 개선 사항

1. 브라우저 인스턴스 풀링으로 성능 향상
2. 캐싱 레이어 추가 (Redis 등)
3. 재시도 로직 추가
4. 더 정확한 가격/할인율 파싱
5. 상품 상세 정보 추가 크롤링 옵션

