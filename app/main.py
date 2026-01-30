"""
Main FastAPI application.
eBay Price Collector API.
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.collectors.ebay import register_ebay_collector
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.models.schemas import HealthResponse
from app.services.currency import get_currency_service

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
    """Application lifespan manager."""
    # Startup
    logger.info("Starting eBay Price Collector API")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
    
    # Register collectors
    register_ebay_collector()
    logger.info("eBay collector registered")
    
    yield
    
    # Shutdown
    logger.info("Shutting down eBay Price Collector API")
    
    # Close database
    await close_db()
    
    # Close currency service
    currency_service = get_currency_service()
    await currency_service.close()


# Create application
app = FastAPI(
    title="eBay Price Collector API",
    description="""
    eBay 상품 가격 수집 및 추적 서비스 API
    
    ## 주요 기능
    
    * **URL 파싱**: eBay 상품 URL에서 itemId 자동 추출
    * **가격 수집**: eBay Browse API 또는 HTML 스크래핑을 통한 가격 정보 수집
    * **상품 검색**: 키워드/브랜드명으로 eBay 상품 검색
    * **가격 추적**: 상품 가격 변동 히스토리 저장 및 조회
    * **가격 알림**: 목표 가격 도달 시 알림 설정
    
    ## 사용 방법
    
    1. Swagger UI에서 각 API 엔드포인트를 테스트할 수 있습니다
    2. 예제 요청 본문을 사용하여 바로 테스트 가능합니다
    3. 모든 API는 JSON 형식으로 요청/응답합니다
    
    ## 인증
    
    현재는 인증이 필요하지 않습니다. (개발 환경)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "root",
            "description": "기본 엔드포인트"
        },
        {
            "name": "health",
            "description": "서비스 상태 확인"
        },
        {
            "name": "price",
            "description": "가격 수집 및 추적 API"
        },
        {
            "name": "search",
            "description": "상품 검색 API"
        }
    ],
    contact={
        "name": "eBay Price Collector",
        "url": "https://github.com/your-repo/ebay-price-collector",
    },
    license_info={
        "name": "MIT",
    },
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
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


# Include API routes
app.include_router(router)

# Include search routes
from app.api.search_routes import router as search_router
app.include_router(search_router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "service": "eBay Price Collector",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns status of all dependencies.
    """
    db_status = "unknown"
    redis_status = "not_configured"
    ebay_api_status = "not_configured"
    
    # Check database
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check eBay API configuration
    if settings.ebay_api_configured:
        ebay_api_status = "configured"
    
    overall_status = "healthy" if db_status == "healthy" else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        database=db_status,
        redis=redis_status,
        ebay_api=ebay_api_status
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
