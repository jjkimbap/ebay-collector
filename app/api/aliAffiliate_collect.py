"""
AliExpress Affiliates API 상품 검색 (python-aliexpress-api 라이브러리 사용)
"""
import re
from typing import Any, Optional

import structlog
from aliexpress_api import AliexpressApi, models
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/ali/affiliate/item_summary/search", tags=["ali-affiliate"])


class SearchItemResponse(BaseModel):
    """검색 결과 개별 아이템"""
    model_config = ConfigDict(extra="allow")  # 추가 필드 허용
    
    itemId: Optional[str] = None
    title: Optional[str] = None
    price: Optional[dict[str, Any]] = None  # 현재 가격 (할인된 가격)
    originalPrice: Optional[dict[str, Any]] = None  # 원래 가격
    discount: Optional[str] = None  # 할인율 (예: "85%")
    rating: Optional[str] = None  # 평점 (예: "4.8")
    sales: Optional[str] = None  # 판매량 (예: "900+", "1.2k")
    condition: Optional[str] = None
    category: Optional[str] = None  # 카테고리
    image: Optional[dict[str, Any]] = None
    itemWebUrl: Optional[str] = None
    commissionRate: Optional[str] = None  # 커미션율 (Affiliates API)


class SearchResponse(BaseModel):
    """검색 응답 모델"""
    success: bool
    total: Optional[int] = None
    itemSummaries: Optional[list[SearchItemResponse]] = None
    error: Optional[str] = None
    debug_info: Optional[dict[str, Any]] = None  # 디버깅 정보 (선택적)


def _normalize_price(price_value: Optional[Any], currency: Optional[str] = None) -> Optional[dict[str, Any]]:
    """가격 값을 정규화"""
    if price_value is None:
        return None
    
    try:
        # 숫자로 변환 시도
        if isinstance(price_value, str):
            # 통화 기호 제거
            price_str = re.sub(r'[^\d.]', '', price_value)
            value = float(price_str)
        else:
            value = float(price_value)
        
        return {
            "value": str(value),
            "currency": currency or "USD"
        }
    except (ValueError, TypeError):
        return None


def _transform_product(product: Any) -> dict[str, Any]:
    """라이브러리 응답의 상품 객체를 표준 형식으로 변환"""
    try:
        # 디버깅: product 객체의 모든 속성 확인 (카테고리 정보 찾기)
        if hasattr(product, '__dict__'):
            product_attrs = dir(product)
            # 카테고리 관련 속성 찾기
            category_attrs = [attr for attr in product_attrs if 'categor' in attr.lower() or 'categor' in str(getattr(product, attr, '')).lower()]
            if category_attrs:
                logger.debug("Found category-related attributes", attrs=category_attrs, 
                           values={attr: getattr(product, attr, None) for attr in category_attrs[:5]})
        
        # 가격 정보 추출
        sale_price = getattr(product, 'sale_price', None) or getattr(product, 'product_price', None)
        original_price = getattr(product, 'original_price', None) or sale_price
        currency = getattr(product, 'target_currency', None) or getattr(product, 'currency', 'USD')
        
        # 할인율 계산
        discount = None
        if original_price and sale_price:
            try:
                orig = float(str(original_price).replace(',', ''))
                sale = float(str(sale_price).replace(',', ''))
                if orig > sale and orig > 0:
                    discount_pct = int(((orig - sale) / orig) * 100)
                    discount = f"{discount_pct}%"
            except Exception:
                pass
        
        # 이미지 URL 추출
        image_url = (
            getattr(product, 'product_main_image_url', None) or
            getattr(product, 'product_image_url', None) or
            getattr(product, 'image_url', None)
        )
        
        # 판매량 추출 및 문자열 변환
        sales = (
            getattr(product, 'volume', None) or
            getattr(product, 'sales', None) or
            getattr(product, 'product_sell_count', None)
        )
        sales_str = str(sales) if sales is not None else None
        
        # 상품 링크 추출
        product_url = (
            getattr(product, 'promotion_link', None) or
            getattr(product, 'product_url', None) or
            getattr(product, 'product_detail_url', None)
        )
        
        # itemId 추출 및 문자열 변환
        item_id = (
            getattr(product, 'product_id', None) or
            getattr(product, 'productId', None) or
            getattr(product, 'id', None)
        )
        
        # 카테고리 정보 추출 (여러 가능한 속성명 확인)
        category = None
        category_candidates = [
            'category_name',
            'category',
            'first_level_category_name',
            'second_level_category_name',
            'product_category_name',
            'categoryName',
            'categoryNamePath',
            'category_name_path',
            'category_path',
            'product_category',
            'category_id_name',
        ]
        
        for attr in category_candidates:
            value = getattr(product, attr, None)
            if value:
                category = str(value)
                break
        
        # 카테고리 ID만 있는 경우 ID를 문자열로 사용
        if not category:
            category_id = getattr(product, 'category_id', None)
            if category_id:
                category = str(category_id)
        
        # 딕셔너리 형태인 경우도 확인
        if not category and isinstance(product, dict):
            for key in category_candidates:
                if key in product and product[key]:
                    category = str(product[key])
                    break
        
        # rating 추출 및 문자열 변환
        rating = (
            getattr(product, 'evaluate_rate', None) or
            getattr(product, 'rating', None) or
            getattr(product, 'product_rating', None)
        )
        rating_str = str(rating) if rating is not None else None
        
        # commissionRate 추출 및 문자열 변환
        commission_rate = (
            getattr(product, 'commission_rate', None) or
            getattr(product, 'commissionRate', None)
        )
        commission_rate_str = str(commission_rate) if commission_rate is not None else None
        
        item = {
            "itemId": str(item_id) if item_id is not None else None,
            "title": (
                getattr(product, 'product_title', None) or
                getattr(product, 'title', None) or
                getattr(product, 'productTitle', None)
            ),
            "price": _normalize_price(sale_price, currency),
            "originalPrice": _normalize_price(original_price, currency),
            "discount": str(discount) if discount is not None else None,
            "rating": rating_str,
            "sales": sales_str,
            "condition": None,
            "category": str(category) if category is not None else None,
            "image": {"imageUrl": image_url} if image_url else None,
            "itemWebUrl": product_url,
            "commissionRate": commission_rate_str,
        }
        
        return item
    except Exception as e:
        logger.error("Failed to transform product", error=str(e), product=product, exc_info=True)
        return {}


def _calculate_keyword_score(keyword: str, title: Optional[str], debug: bool = False) -> float:
    """키워드와 제목의 관련도 점수 계산 (0.0 ~ 1.0)"""
    if not title:
        return 0.0
    
    keyword_lower = keyword.lower().strip()
    title_lower = title.lower().strip()
    
    # 키워드가 정확히 일치하는 경우
    if keyword_lower == title_lower:
        return 1.0
    
    # 키워드가 제목에 정확히 포함된 경우 (공백/특수문자 무시)
    # 공백과 특수문자를 제거한 버전으로도 확인
    keyword_clean = re.sub(r'[^\w가-힣]', '', keyword_lower)
    title_clean = re.sub(r'[^\w가-힣]', '', title_lower)
    
    if keyword_clean in title_clean:
        # 제목의 앞부분에 있을수록 높은 점수
        position = title_clean.find(keyword_clean)
        position_score = 1.0 - (position / max(len(title_clean), 100))
        return 0.8 + (position_score * 0.2)
    
    # 원본에서도 확인 (공백이 있는 경우 대비)
    if keyword_lower in title_lower:
        position = title_lower.find(keyword_lower)
        position_score = 1.0 - (position / max(len(title_lower), 100))
        return 0.8 + (position_score * 0.2)
    
    # 키워드를 단어로 분리하여 매칭 (한글/영문/숫자 모두 고려)
    # 한글, 영문, 숫자를 각각 분리
    # 예: "3CE립스틱" -> ["3ce", "립스틱"]
    # 예: "3celipstic" -> ["3ce", "lipstic"] (오타 포함)
    keyword_parts = []
    remaining_text = keyword_clean  # 처리할 남은 텍스트
    
    # 방법 1: 숫자+영문 조합 추출 (예: "3ce", "3ce123")
    # 패턴: 숫자로 시작하는 영문 조합
    num_eng_matches = list(re.finditer(r'\d+[a-z]+', keyword_clean))
    for match in num_eng_matches:
        part = match.group()
        keyword_parts.append(part)
        # 해당 부분을 제거하여 나머지 텍스트에서 추가 단어 추출
        remaining_text = remaining_text.replace(part, ' ', 1)
    
    # 방법 2: 남은 텍스트에서 순수 영문 단어 추출 (2글자 이상)
    remaining_clean = re.sub(r'[^\w가-힣]', '', remaining_text)
    eng_words = re.findall(r'[a-z]{2,}', remaining_clean)
    keyword_parts.extend(eng_words)
    
    # 방법 3: 한글 부분 추출 (전체 키워드에서)
    korean_parts = re.findall(r'[가-힣]+', keyword_lower)
    keyword_parts.extend(korean_parts)
    
    # 방법 4: 공백/특수문자로도 분리 시도 (키워드가 분리되지 않은 경우)
    if not keyword_parts:
        keyword_parts = [w.strip() for w in re.split(r'[\s\-_]+', keyword_lower) if len(w.strip()) >= 1]
    
    # 중복 제거 및 최소 2글자 이상인 부분만 사용 (1글자는 너무 일반적)
    seen = set()
    keyword_words = []
    for w in keyword_parts:
        w_clean = w.strip()
        if len(w_clean) >= 2 and w_clean not in seen:
            seen.add(w_clean)
            keyword_words.append(w_clean)
    
    # 키워드가 너무 짧아서 분리되지 않은 경우, 전체 키워드를 사용
    if not keyword_words and len(keyword_clean) >= 2:
        keyword_words = [keyword_clean]
    
    # 디버깅: 키워드 분리 결과 로깅 (처음 몇 번만)
    if debug and keyword_words:
        logger.debug("Keyword parts extracted", 
                     keyword=keyword,
                     parts=keyword_words,
                     title_preview=title_lower[:50])
    
    if not keyword_words:
        # 키워드가 너무 짧은 경우 (1글자) 전체 키워드로 매칭 시도
        if len(keyword_clean) >= 1:
            if keyword_clean in title_clean:
                return 0.3
        return 0.0
    
    # 각 단어가 제목에 포함되는지 확인 (공백 제거 버전도 확인)
    matched_words = 0
    for word in keyword_words:
        # 원본 제목에서 확인
        if word in title_lower:
            matched_words += 1
        # 공백 제거 버전에서도 확인
        elif word in title_clean:
            matched_words += 1
        # 부분 매칭도 고려 (예: "lipstic"이 "lipstick"에 포함되는지)
        else:
            # 제목의 각 단어와 비교
            title_words = re.findall(r'[a-z0-9가-힣]+', title_lower)
            for title_word in title_words:
                # 키워드가 제목 단어에 포함되거나, 제목 단어가 키워드에 포함되는 경우
                if word in title_word or title_word in word:
                    # 유사도가 높은 경우만 매칭으로 간주 (길이 차이가 2글자 이내)
                    if abs(len(word) - len(title_word)) <= 2:
                        matched_words += 1
                        break
    
    match_ratio = matched_words / len(keyword_words) if keyword_words else 0
    
    # 모든 단어가 매칭되면 높은 점수
    if match_ratio == 1.0:
        return 0.7
    
    # 일부 단어만 매칭되면 낮은 점수 (하지만 0이 아닌 점수 반환)
    # 최소 1개 단어라도 매칭되면 점수 부여
    if match_ratio > 0:
        # 매칭 비율에 따라 점수 계산 (최소 0.3 이상)
        base_score = match_ratio * 0.5
        # 최소 1개 단어라도 매칭되면 최소 0.3 점수 부여
        return max(base_score, 0.3)
    
    # 단어 매칭이 없어도 부분 문자열 매칭 시도
    # 예: "3ce"가 "3ce lipstick"에 포함되는지 확인
    for word in keyword_words:
        if len(word) >= 2:
            if word in title_lower or word in title_clean:
                return 0.2  # 부분 매칭 시 최소 점수
    
    # 최후의 수단: 키워드의 일부라도 포함되면 점수 부여
    if len(keyword_clean) >= 2:
        # 키워드의 앞부분이 제목에 포함되는지 확인
        for i in range(len(keyword_clean), 1, -1):
            partial = keyword_clean[:i]
            if partial in title_clean:
                return 0.1  # 부분 매칭 최소 점수
    
    return 0.0


def _filter_and_sort_by_relevance(items: list[dict[str, Any]], keyword: str, require_keyword: bool = True) -> list[dict[str, Any]]:
    """키워드 관련도에 따라 필터링 및 정렬"""
    scored_items = []
    
    logger.debug("Filtering items by keyword relevance", 
                total_items=len(items), 
                keyword=keyword, 
                require_keyword=require_keyword)
    
    for item in items:
        title = item.get('title', '')
        # 처음 몇 개 아이템에 대해서만 디버깅 모드 활성화
        debug_mode = len(scored_items) < 5
        score = _calculate_keyword_score(keyword, title, debug=debug_mode)
        
        # 디버깅: 첫 몇 개 아이템의 점수 로깅 (INFO 레벨로 변경하여 항상 표시)
        if debug_mode:
            logger.info("Item relevance score", 
                        title=title[:80] if title else None,
                        score=score,
                        keyword=keyword,
                        will_include=score >= (0.05 if any('\uac00' <= char <= '\ud7a3' for char in keyword) else 0.1))
        
        # 키워드가 제목에 포함되지 않은 경우 필터링
        # require_keyword가 False이면 모든 아이템 포함 (점수만으로 정렬)
        # 한글 키워드의 경우 더 낮은 임계값 사용 (0.05로 완화)
        # 영문/숫자 키워드도 더 완화된 임계값 사용 (0.1로 완화 - 오타 고려)
        if any('\uac00' <= char <= '\ud7a3' for char in keyword):
            threshold = 0.05  # 한글 키워드는 매우 낮은 임계값
        else:
            threshold = 0.1  # 영문/숫자 키워드도 완화 (오타 고려하여 더 낮게 설정)
        
        if require_keyword and score < threshold:
            # 필터링되는 아이템도 로깅 (처음 3개만)
            if len(scored_items) < 3:
                logger.debug("Item filtered out", 
                           title=title[:50] if title else None,
                           score=score,
                           threshold=threshold,
                           keyword=keyword)
            continue
        
        # 점수를 아이템에 추가
        item_with_score = item.copy()
        item_with_score['_relevance_score'] = score
        scored_items.append(item_with_score)
    
    logger.info("Filtered items by relevance", 
               original_count=len(items),
               filtered_count=len(scored_items),
               require_keyword=require_keyword)
    
    # 관련도 점수로 정렬 (높은 점수 우선)
    scored_items.sort(key=lambda x: x.get('_relevance_score', 0), reverse=True)
    
    # 점수 필드 제거
    for item in scored_items:
        item.pop('_relevance_score', None)
    
    return scored_items


@router.get("", response_model=SearchResponse)
async def search_products(
    keyword: str = Query(..., description="검색 키워드"),
    limit: int = Query(3, ge=1, le=200, description="결과 수 (최대 200)"),
    min_price: Optional[float] = Query(None, description="최소 가격"),
    max_price: Optional[float] = Query(None, description="최대 가격"),
    category_ids: Optional[str] = Query(None, description="카테고리 ID (쉼표로 구분)"),
    target_currency: str = Query("KRW", description="통화 (USD, KRW 등)"),
    target_language: str = Query("KO", description="언어 (EN, KO 등)"),
    sort: Optional[str] = Query(None, description="정렬 방식 (SALE_PRICE_ASC, SALE_PRICE_DESC, SALE_NUM_DESC 등)"),
    tracking_id: Optional[str] = Query(None, description="트래킹 ID"),
    ship_to_country: Optional[str] = Query("KR", description="배송 국가 코드 (US, KR 등)"),
    require_keyword_in_title: bool = Query(True, description="제목에 키워드 포함 필수 여부"),
    fetch_more_for_filtering: bool = Query(True, description="필터링을 위해 더 많은 결과 가져오기 (정확도 향상)"),
):
    """
    AliExpress Affiliates API를 사용한 상품 검색 (python-aliexpress-api 라이브러리 사용)
    
    **정확도 향상 기능:**
    - 키워드 관련도 점수 계산 및 정렬
    - 제목에 키워드가 포함된 상품 우선 반환
    - 필터링을 위해 더 많은 결과를 가져온 후 관련도 순으로 정렬
    
    **필수 설정 (.env):**
    - ALI_AFFILIATE_APP_KEY: App Key
    - ALI_AFFILIATE_APP_SECRET: App Secret
    
    **파라미터:**
    - require_keyword_in_title: True인 경우 제목에 키워드가 포함된 상품만 반환 (기본값: True)
    - fetch_more_for_filtering: True인 경우 필터링을 위해 더 많은 결과를 가져옴 (기본값: True)
    - sort: 정렬 방식 (지정하지 않으면 관련도 순)
    
    **수집 정보:**
    - 상품 제목, 가격, 원래 가격, 할인율
    - 평점, 판매량
    - 카테고리
    - 상품 이미지, 링크
    - 커미션율 (Affiliates API 전용)
    """
    settings = get_settings()
    
    # 설정 확인
    app_key = getattr(settings, 'ali_affiliate_app_key', '') or settings.ali_api_key
    app_secret = getattr(settings, 'ali_affiliate_app_secret', '') or ''
    
    if not app_key or not app_secret:
        logger.error("AliExpress Affiliates API credentials not configured")
        return SearchResponse(
            success=False,
            error="AliExpress Affiliates API credentials not configured. Please set ALI_AFFILIATE_APP_KEY and ALI_AFFILIATE_APP_SECRET"
        )
    
    logger.info("AliExpress Affiliates API search request", query=keyword, limit=limit)
    
    try:
        # AliexpressApi 클라이언트 생성 (key와 secret은 위치 인자, language와 currency는 키워드 인자)
        aliexpress = AliexpressApi(
            app_key,  # 위치 인자: key
            app_secret,  # 위치 인자: secret
            language=target_language,
            currency=target_currency
        )
        
        # get_products 메서드 호출 (제공된 예제 기반)
        # 기본 파라미터 구성
        get_products_params: dict[str, Any] = {
            'keywords': keyword,
        }
        
        # 선택적 파라미터 추가
        if max_price is not None:
            get_products_params['max_sale_price'] = max_price
        if min_price is not None:
            get_products_params['min_sale_price'] = min_price
        if category_ids:
            get_products_params['category_ids'] = category_ids
        if target_currency:
            get_products_params['target_currency'] = target_currency
        if target_language:
            get_products_params['target_language'] = target_language
        if tracking_id:
            get_products_params['tracking_id'] = tracking_id
        if ship_to_country:
            get_products_params['ship_to_country'] = ship_to_country
        
        # 페이지 크기 설정 (필터링을 위해 더 많이 가져오기)
        # 정확도를 높이기 위해 limit보다 더 많은 결과를 가져온 후 필터링
        if fetch_more_for_filtering:
            # 필터링을 위해 limit의 2-3배를 가져옴 (최대 50개)
            page_size = min(limit * 3, 50)
        else:
            page_size = min(limit, 50)
        get_products_params['page_size'] = page_size
        
        # 정렬 방식 설정 (지정되지 않은 경우 관련도 우선)
        if not sort:
            # AliExpress API의 관련도 정렬 옵션 (지원되는 경우)
            # 일반적으로 정렬을 지정하지 않으면 관련도 순으로 반환됨
            pass
        else:
            get_products_params['sort'] = sort
        
        # 카테고리 정보를 포함하도록 fields 파라미터 추가 (지원되는 경우)
        # AliExpress Affiliates API는 fields 파라미터로 필요한 필드를 지정할 수 있음
        if 'fields' not in get_products_params:
            get_products_params['fields'] = (
                'product_id,product_title,sale_price,original_price,'
                'product_main_image_url,promotion_link,evaluate_rate,volume,'
                'category_name,category_id,first_level_category_name,second_level_category_name,'
                'commission_rate'
            )
        
        # API 호출
        logger.info("Calling AliExpress API", params=get_products_params, keyword=keyword)
        try:
            response = aliexpress.get_products(**get_products_params)
        except Exception as api_error:
            logger.error("API call failed", error=str(api_error), exc_info=True)
            return SearchResponse(
                success=False,
                error=f"AliExpress API call failed: {str(api_error)}"
            )
        
        # 원문 응답 로깅 (디버깅용)
        logger.info("AliExpress API raw response", 
                   response_type=type(response).__name__,
                   has_products_attr=hasattr(response, 'products'),
                   response_dict_keys=list(response.__dict__.keys()) if hasattr(response, '__dict__') else None,
                   keyword=keyword)
        
        # 응답 객체의 전체 구조 확인
        if hasattr(response, '__dict__'):
            response_attrs = {k: str(v)[:100] for k, v in list(response.__dict__.items())[:10]}
            logger.info("Response attributes sample", attrs=response_attrs, keyword=keyword)
            
            # products 속성이 있는지 확인
            if 'products' in response.__dict__:
                products_value = response.__dict__['products']
                logger.info("Products attribute found in response.__dict__", 
                           type=type(products_value).__name__,
                           is_list=isinstance(products_value, list),
                           length=len(products_value) if isinstance(products_value, list) else "N/A",
                           keyword=keyword)
        
        # 응답 처리
        if not response:
            logger.warning("No response from AliExpress API")
            return SearchResponse(
                success=False,
                error="No response from AliExpress API"
            )
        
        # products 추출
        products = []
        if hasattr(response, 'products') and response.products:
            products = response.products
            products_count = len(products) if isinstance(products, list) else (1 if products else 0)
            logger.info("Found products via response.products", 
                       count=products_count,
                       is_list=isinstance(products, list),
                       keyword=keyword)
            # 첫 번째 상품의 속성 확인
            if products and len(products) > 0:
                first_product = products[0]
                first_title = getattr(first_product, 'product_title', None) or getattr(first_product, 'title', None)
                first_id = getattr(first_product, 'product_id', None)
                logger.info("First product sample", 
                           product_title=first_title[:100] if first_title else None,
                           product_id=first_id,
                           keyword=keyword)
                # 첫 번째 상품의 모든 속성 확인 (디버깅용)
                if hasattr(first_product, '__dict__'):
                    first_product_attrs = list(first_product.__dict__.keys())[:20]
                    logger.debug("First product attributes", attrs=first_product_attrs)
        elif isinstance(response, dict) and 'products' in response:
            products = response['products']
            logger.info("Found products via dict['products']", 
                       count=len(products) if isinstance(products, list) else "not a list",
                       keyword=keyword)
        elif isinstance(response, list):
            products = response
            logger.info("Response is list", count=len(products), keyword=keyword)
        else:
            logger.warning("Could not extract products from response", 
                          response_type=type(response).__name__,
                          keyword=keyword,
                          response_repr=str(response)[:200])
        
        if not products:
            logger.warning("No products found in API response", 
                          response_type=type(response).__name__,
                          keyword=keyword,
                          params=get_products_params,
                          response_repr=str(response)[:500] if response else "None",
                          has_response=response is not None)
            # 필터링 없이도 결과가 없는 경우 안내 메시지 추가
            debug_info = {
                "response_type": type(response).__name__ if response else None,
                "has_products_attr": hasattr(response, 'products') if response else False,
                "response_keys": list(response.__dict__.keys()) if (response and hasattr(response, '__dict__')) else None,
            }
            return SearchResponse(
                success=True,
                total=0,
                itemSummaries=None,
                error=f"No products found for keyword '{keyword}'. Try with require_keyword_in_title=false or check if the keyword exists on AliExpress.",
                debug_info=debug_info
            )
        
        logger.info("Processing products", 
                   products_count=len(products),
                   keyword=keyword,
                   require_keyword_in_title=require_keyword_in_title)
        
        # 상품 데이터 변환
        items = []
        for idx, product in enumerate(products):
            try:
                item = _transform_product(product)
                if item and item.get('title'):  # 제목이 있는 경우만 추가
                    items.append(item)
                    # 처음 3개 아이템의 제목 로깅 (INFO 레벨로 변경)
                    if idx < 3:
                        logger.info("Transformed product", 
                                   index=idx,
                                   title=item.get('title', '')[:100],
                                   keyword=keyword)
                else:
                    logger.info("Product missing title", index=idx, keyword=keyword)
            except Exception as e:
                logger.debug("Failed to transform product", error=str(e), index=idx)
                continue
        
        logger.info("Transformed products", 
                   transformed_count=len(items),
                   original_count=len(products),
                   keyword=keyword)
        
        # 변환된 아이템이 없는 경우
        if not items:
            logger.warning("No items after transformation", 
                          products_count=len(products),
                          keyword=keyword)
            # 첫 번째 상품의 제목 샘플 로깅
            if products and len(products) > 0:
                first_product = products[0]
                first_title = getattr(first_product, 'product_title', None) or getattr(first_product, 'title', None)
                logger.info("First product title sample", 
                           title=first_title[:200] if first_title else None,
                           keyword=keyword)
            return SearchResponse(
                success=True,
                total=0,
                itemSummaries=None,
                error=f"No items could be transformed. API returned {len(products)} products but transformation failed.",
            )
        
        # 키워드 관련도에 따라 필터링 및 정렬
        items_before_filter = len(items)
        if items:
            items = _filter_and_sort_by_relevance(items, keyword, require_keyword_in_title)
            logger.info("Filtered and sorted by relevance", 
                       original_count=len(products),
                       transformed_count=items_before_filter,
                       filtered_count=len(items),
                       keyword=keyword,
                       require_keyword_in_title=require_keyword_in_title)
        else:
            logger.warning("No items after transformation", 
                          products_count=len(products),
                          keyword=keyword)
        
        # limit만큼만 반환
        items = items[:limit] if items else []
        
        # 필터링으로 인해 결과가 없는 경우 안내
        if not items and items_before_filter > 0:
            logger.warning("All items filtered out", 
                          before_filter=items_before_filter,
                          keyword=keyword,
                          require_keyword_in_title=require_keyword_in_title)
            # 필터링 전 아이템들의 제목 샘플 제공
            debug_info = {
                "filtered_out_count": items_before_filter,
                "keyword": keyword,
                "require_keyword_in_title": require_keyword_in_title,
                "suggestion": "Try with require_keyword_in_title=false to see all results"
            }
            return SearchResponse(
                success=True,
                total=0,
                itemSummaries=None,
                error=f"Found {items_before_filter} products but all were filtered out. Try with require_keyword_in_title=false to see all results.",
                debug_info=debug_info
            )
        
        return SearchResponse(
            success=True,
            total=len(items),
            itemSummaries=items if items else None,
        )
    
    except Exception as e:
        logger.error("AliExpress Affiliates API error", error=str(e), exc_info=True)
        return SearchResponse(
            success=False,
            error=f"AliExpress Affiliates API error: {str(e)}"
        )
