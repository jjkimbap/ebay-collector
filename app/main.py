"""
Main FastAPI application.
eBay 상품 검색 API.
"""
import asyncio
import sys
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings

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

# Create application
app = FastAPI(
    title="상품 검색 API",
    description="""
    다양한 플랫폼의 상품 검색 API
    
    ## 지원 플랫폼
    
    * **eBay**: eBay Browse API를 사용한 상품 검색
    * **AliExpress**: AliExpress API를 사용한 상품 검색
    * **Amazon**: Amazon Product Advertising API를 사용한 상품 검색
    
    ## 사용 방법
    
    1. Swagger UI에서 API 엔드포인트를 테스트할 수 있습니다
    2. 각 플랫폼별로 검색 키워드를 입력하여 상품을 검색합니다
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
from app.api.ebay_collect import router as ebay_router
from app.api.ali_collect import router as ali_router
from app.api.amazon_collect import router as amazon_router

app.include_router(ebay_router)
app.include_router(ali_router)
app.include_router(amazon_router)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
