"""
Main FastAPI application.
eBay 상품 검색 API.
"""
import asyncio
import sys
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.scheduler import setup_scheduler, shutdown_scheduler

# Ensure subprocess support for Playwright on Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시 스케줄러 시작
    setup_scheduler()
    logger.info("Application started")
    yield
    # 종료 시 스케줄러 종료
    shutdown_scheduler()
    logger.info("Application shutdown")


# Create application
app = FastAPI(
    title="상품 검색 API",
    description="""
    다양한 플랫폼의 상품 검색 API
    
    ## 지원 플랫폼
    
    * (미서비스) eBay:
        1. eBay Browse API를 사용한 상품 검색
        2. eBay Item API를 사용한 상품 상세 정보 조회
    * (미서비스) AliExpress: 
        1. Playwright를 사용한 상품 검색
        2. AliExpress Affiliates API를 사용한 상품 검색
    * Amazon: playwright를 사용한 상품 검색
    
    ## 사용 방법
    
    1. Swagger UI에서 API 엔드포인트를 테스트할 수 있습니다
    2. 각 플랫폼별로 검색 키워드를 입력하여 상품을 검색합니다
    
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc)
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.app_debug else None
        }
    )

# Include collector routes
from app.api.ebay_collect import search_router as ebay_search_router, item_router as ebay_item_router
from app.api.ali_collect import router as ali_router
from app.api.amazon_collect import router as amazon_router
from app.api.aliAffiliate_collect import router as ali_affiliate_router
from app.api.customer_keywords import router as customer_keywords_router
from app.api.crawl_amazon import router as crawl_amazon_router

# app.include_router(ebay_search_router)  # eBay Browse API를 사용한 상품 검색 : 제거 (리뷰수나 판매수 수집이 어려워 비교가 힘듦)
# app.include_router(ebay_item_router)  # eBay Item API를 사용한 상품 상세 정보 조회 API : 제거 (상세 정보에서도 리뷰수나 판매수 수집이 어려워 비교가 힘듦)
app.include_router(amazon_router)  # Amazon 상품 검색
# app.include_router(ali_router)  # AliExpress Playwright를 사용한 상품 검색 : 제거 (bot에 걸리는 빈도수가 너무 잦음)
# app.include_router(ali_affiliate_router)  # AliExpress Affiliates API를 사용한 상품 검색 : 제거 (키워드 검색 정확도가 굉장히 낮음)

app.include_router(customer_keywords_router)  # 고객 코드와 레벨을 통한 정보 조회 API
app.include_router(crawl_amazon_router)  # 고객 코드와 레벨을 통한 Amazon 상품 크롤링 API



if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
