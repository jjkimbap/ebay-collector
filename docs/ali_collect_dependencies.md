# AliExpress 상품 검색 API 의존성 문서

## 개요
`app/api/ali_collect.py`는 AliExpress 상품 검색을 위한 FastAPI 엔드포인트를 제공합니다. Playwright를 사용하여 웹 크롤링을 수행합니다.

## 파일 구조

### 직접 의존 파일
```
app/api/ali_collect.py
├── app/lib/commerce_playwright.py  (크롤링 로직)
│   ├── app/core/config.py          (설정 관리)
│   └── [외부 라이브러리들]
└── [FastAPI 관련 라이브러리들]
```

### 파일 상세

#### 1. `app/api/ali_collect.py`
- **역할**: FastAPI 라우터 정의 및 요청/응답 처리
- **주요 기능**:
  - GET `/api/ali/item_summary/search` 엔드포인트 제공
  - 요청 파라미터 검증 (keyword, limit)
  - 응답 모델 정의 (SearchItemResponse, SearchResponse)
  - 에러 처리

#### 2. `app/lib/commerce_playwright.py`
- **역할**: Playwright를 사용한 통합 크롤링 엔진
- **주요 기능**:
  - `EcommerceScraper` 클래스: 브라우저 자동화 및 크롤링
  - `scrape_aliexpress()`: AliExpress 전용 크롤링 메서드
  - `search_items()`: 비동기 래퍼 함수
  - 데이터 정규화 및 파싱 유틸리티

#### 3. `app/core/config.py`
- **역할**: 애플리케이션 설정 관리
- **주요 설정**:
  - `playwright_headless`: 브라우저 헤드리스 모드
  - `playwright_proxy`: 프록시 설정 (선택)
  - `playwright_amazon_domain`: Amazon 도메인 설정
  - `playwright_ebay_domain`: eBay 도메인 설정

## 라이브러리 의존성

### 필수 라이브러리

#### FastAPI 관련
- `fastapi==0.109.0`: 웹 프레임워크
- `pydantic==2.5.3`: 데이터 검증 및 직렬화
- `pydantic-settings==2.1.0`: 설정 관리

#### Playwright 관련
- `playwright==1.42.0`: 브라우저 자동화
- `playwright-stealth==1.0.6`: 봇 탐지 회피 (선택적)

#### 비동기 처리
- `anyio`: 비동기 작업을 동기 함수로 실행

#### 로깅
- `structlog==24.1.0`: 구조화된 로깅

### 표준 라이브러리
- `typing`: 타입 힌팅
- `dataclasses`: 데이터 클래스
- `random`: 랜덤 값 생성 (User-Agent 랜덤화)
- `re`: 정규표현식 (가격, 할인율 파싱)
- `time`: 시간 지연 (인간처럼 보이는 동작)
- `urllib.parse`: URL 인코딩

## 데이터 흐름

```
1. HTTP 요청
   GET /api/ali/item_summary/search?keyword=3ce&limit=10
   ↓
2. ali_collect.py
   - 파라미터 검증
   - search_items("aliexpress", keyword, limit) 호출
   ↓
3. commerce_playwright.py
   - anyio.to_thread.run_sync()로 동기 함수 실행
   - EcommerceScraper 컨텍스트 매니저로 브라우저 시작
   - scrape_aliexpress() 실행
     - Playwright로 AliExpress 검색 페이지 접속
     - 상품 정보 추출 (제목, 가격, 이미지, 링크)
     - 데이터 정규화 및 중복 제거
   ↓
4. 응답 반환
   - SearchResponse 모델로 변환
   - JSON 응답 반환
```

## 설정 요구사항

### 환경 변수 (.env)
```env
# Playwright 설정
PLAYWRIGHT_HEADLESS=false          # 브라우저 헤드리스 모드 (기본값: false)
PLAYWRIGHT_PROXY=                  # 프록시 서버 (선택, 예: http://proxy:8080)
PLAYWRIGHT_AMAZON_DOMAIN=com       # Amazon 도메인 (기본값: com)
PLAYWRIGHT_EBAY_DOMAIN=com         # eBay 도메인 (기본값: com)
```

### Playwright 브라우저 설치
```bash
playwright install chromium
```

## 타임아웃 설정
- 페이지 로드 타임아웃: **10분 (600,000ms)**
- Selector 대기 타임아웃: **10분 (600,000ms)**
- 기본 작업 타임아웃: **10분 (600,000ms)**

## 에러 처리
- 타임아웃: 10분 초과 시 에러 반환
- Selector 미발견: 경고 로그 후 계속 진행
- 네트워크 오류: 에러 로그 및 실패 응답 반환

## 성능 고려사항
- 브라우저 인스턴스는 요청마다 새로 생성 (컨텍스트 매니저 사용)
- 인간처럼 보이는 동작: 1-2.8초 랜덤 지연
- User-Agent 랜덤화로 봇 탐지 회피
- Stealth 플러그인 사용 (선택적)

