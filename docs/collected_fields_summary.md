# 수집 가능한 정보 요약

각 플랫폼별로 수집 가능한 상품 정보 필드를 정리한 문서입니다.

## 📦 eBay

### 검색 API (`GET /api/ebay/item_summary/search`)
- ✅ `itemId`: 상품 ID
- ✅ `title`: 상품 제목
- ✅ `price`: 가격 정보 (value, currency)
- ✅ `condition`: 상품 상태
- ✅ `image`: 이미지 정보
- ✅ `itemWebUrl`: 상품 페이지 URL
- ✅ 기타 eBay API 원본 필드 (extra="allow"로 모든 필드 포함)

### 상세 정보 API (`GET /api/ebay/item/{item_id}`)
- ✅ `itemId`: 상품 ID
- ✅ `title`: 상품 제목
- ✅ `shortDescription`: 요약 설명
- ✅ `price`: 가격 정보 (value, currency)
- ✅ `categoryPath`: 카테고리 경로
- ✅ `categoryIdPath`: 카테고리 ID 경로
- ✅ `condition`: 상품 상태
- ✅ `conditionId`: 상품 상태 ID
- ✅ `itemLocation`: 상품 위치 (city, stateOrProvince, postalCode, country)
- ✅ `image`: 이미지 정보
- ✅ `brand`: 브랜드
- ✅ `seller`: 판매자 정보
  - `username`: 판매자 이름
  - `feedbackPercentage`: 피드백 퍼센트
  - `feedbackScore`: 피드백 점수
- ✅ `mpn`: 제조사 부품 번호
- ✅ `estimatedAvailabilities`: 예상 재고 정보
- ✅ `shippingOptions`: 배송 옵션
  - `shippingServiceCode`: 배송 서비스 코드
  - `shippingCost`: 배송비 (value, currency)
  - `minEstimatedDeliveryDate`: 최소 배송 예상일
  - `maxEstimatedDeliveryDate`: 최대 배송 예상일
- ✅ `shipToLocations`: 배송 가능 지역
- ✅ `returnTerms`: 반품 조건
- ✅ `taxes`: 세금 정보
- ✅ `localizedAspects`: 지역화된 속성
- ✅ `primaryProductReviewRating`: 리뷰 평점 정보
  - `reviewCount`: 리뷰 수
  - `averageRating`: 평균 평점
  - `ratingHistograms`: 평점 히스토그램
- ✅ `priorityListing`: 우선순위 리스팅 여부
- ✅ `topRatedBuyingExperience`: 최고 등급 구매 경험 여부
- ✅ `buyingOptions`: 구매 옵션
- ✅ `itemWebUrl`: 상품 페이지 URL
- ✅ `description`: 상품 설명
- ✅ `paymentMethods`: 결제 방법
- ✅ `immediatePay`: 즉시 결제 가능 여부
- ✅ `eligibleForInlineCheckout`: 인라인 체크아웃 가능 여부
- ✅ `lotSize`: 로트 크기
- ✅ `legacyItemId`: 레거시 아이템 ID
- ✅ `adultOnly`: 성인 전용 여부
- ✅ `categoryId`: 카테고리 ID

## 🛒 Amazon

### 검색 API (`GET /api/amazon/item_summary/search`)
- ✅ `itemId`: ASIN (Amazon Standard Identification Number)
- ✅ `title`: 상품 제목
- ✅ `price`: 현재 가격 (value, currency)
- ✅ `originalPrice`: 원래 가격 (할인 전)
- ✅ `discount`: 할인율 (예: "25%")
- ✅ `rating`: 평점 (예: "4.5")
- ✅ `reviews`: 리뷰 수 (예: "1,234")
- ✅ `condition`: 상품 상태 (예: "New", "Used")
- ✅ `category`: 카테고리 (예: "Beauty & Personal Care > Makeup")
- ✅ `seller`: 판매자 정보
  - `username`: 판매자 이름/사용자명
  - `feedbackPercentage`: 피드백 퍼센트 (예: "99.7")
  - `feedbackScore`: 피드백 점수/리뷰 수 (예: "1733")
- ✅ `image`: 이미지 정보 (imageUrl)
- ✅ `itemWebUrl`: 상품 페이지 URL

## 🛍️ AliExpress (Playwright)

### 검색 API (`GET /api/ali/item_summary/search`)
- ✅ `itemId`: 상품 ID
- ✅ `title`: 상품 제목
- ✅ `price`: 현재 가격 (value, currency)
- ✅ `originalPrice`: 원래 가격
- ✅ `discount`: 할인율 (예: "85%")
- ✅ `rating`: 평점 (예: "4.8")
- ✅ `sales`: 판매량 (예: "900+", "1.2k")
- ✅ `condition`: 상품 상태
- ✅ `category`: 카테고리 (예: "Beauty & Personal Care > Makeup")
- ✅ `image`: 이미지 정보 (imageUrl)
- ✅ `itemWebUrl`: 상품 페이지 URL

## 🛍️ AliExpress (Affiliates API)

### 검색 API (`GET /api/ali-affiliate/item_summary/search`)
- ✅ `itemId`: 상품 ID
- ✅ `title`: 상품 제목
- ✅ `price`: 현재 가격 (value, currency)
- ✅ `originalPrice`: 원래 가격
- ✅ `discount`: 할인율 (예: "85%")
- ✅ `rating`: 평점 (예: "4.8")
- ✅ `sales`: 판매량 (예: "900+", "1.2k")
- ✅ `condition`: 상품 상태
- ✅ `category`: 카테고리
- ✅ `image`: 이미지 정보 (imageUrl)
- ✅ `itemWebUrl`: 상품 페이지 URL
- ✅ `commissionRate`: 커미션율 (Affiliates API 전용)

## 📊 공통 필드

모든 플랫폼에서 공통으로 수집하는 필드:
- ✅ `itemId`: 상품 고유 ID
- ✅ `title`: 상품 제목
- ✅ `price`: 현재 가격 (value, currency)
- ✅ `originalPrice`: 원래 가격 (할인 전)
- ✅ `discount`: 할인율
- ✅ `rating`: 평점
- ✅ `image`: 이미지 정보
- ✅ `itemWebUrl`: 상품 페이지 URL

## 🔍 플랫폼별 특화 필드

### eBay만 수집 가능
- 판매자 피드백 정보 (상세)
- 배송 옵션 상세 정보
- 세금 정보
- 반품 조건
- 리뷰 평점 히스토그램

### Amazon만 수집 가능
- 판매자 피드백 정보 (상세)
- ASIN (Amazon Standard Identification Number)
- 리뷰 수

### AliExpress만 수집 가능
- 판매량 (sales)
- 커미션율 (Affiliates API)

## 📝 참고사항

- 모든 필드는 `Optional`이며, 플랫폼이나 상품에 따라 일부 필드가 `null`일 수 있습니다.
- `extra="allow"` 설정으로 API 원본 응답의 추가 필드도 포함됩니다.
- 가격 정보는 항상 `{value: string, currency: string}` 형식으로 반환됩니다.
