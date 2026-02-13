"""
스케줄러 설정
"""
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import structlog

from app.services.crawl_service import crawl_amazon_batch
from app.services.keyword_service import get_customer_keywords

logger = structlog.get_logger()

# 한국 시간대 설정 (Python 3.9+ 표준 라이브러리 사용)
KST = ZoneInfo("Asia/Seoul")

# 타임존을 명시적으로 설정한 스케줄러
scheduler = AsyncIOScheduler(timezone=KST)


async def scheduled_crawl_amazon():
    """
    매일 오후 4시에 실행되는 스케줄된 크롤링 작업
    
    price_level=2인 모든 고객에 대해 크롤링을 실행합니다.
    """
    price_level = 2
    limit = 20  # 각 키워드당 수집할 상품 수
    
    logger.info("Scheduled crawl started", price_level=price_level, limit=limit)
    
    try:
        # Step 1: price_level로 모든 고객 조회
        keywords_list = await get_customer_keywords(
            customer_cd=None,  # None이면 모든 고객 조회
            price_level=price_level
        )
        
        if not keywords_list:
            logger.warning("No customers found for scheduled crawl", price_level=price_level)
            return
        
        # customer_cd 리스트 추출
        customer_cds = [kw.customerCd for kw in keywords_list if kw.customerCd]
        
        if not customer_cds:
            logger.warning("No valid customer_cd found for scheduled crawl")
            return
        
        logger.info(
            "Scheduled crawl - customers retrieved",
            price_level=price_level,
            customer_count=len(customer_cds)
        )
        
        # Step 2: 배치 크롤링 실행
        result = await crawl_amazon_batch(
            customer_cds=customer_cds,
            price_level=price_level,
            limit=limit,
        )
        
        if result.get("success"):
            logger.info(
                "Scheduled crawl completed successfully",
                total_customers=result.get("total_customers"),
                processed_customers=result.get("processed_customers"),
                total_items=result.get("total_items"),
                saved_items=result.get("saved_items"),
            )
        else:
            logger.error(
                "Scheduled crawl failed",
                error=result.get("error"),
                errors=result.get("errors", [])
            )
            
    except Exception as e:
        logger.error(
            "Scheduled crawl error",
            error=str(e),
            exc_info=True
        )


def setup_scheduler():
    """스케줄러를 설정하고 시작합니다."""
    # 매일 오후 4시에 실행 (KST 기준)
    scheduler.add_job(
        scheduled_crawl_amazon,
        trigger=CronTrigger(hour=16, minute=0, timezone=KST),
        id="daily_amazon_crawl",
        name="Daily Amazon Crawl at 4 PM",
        replace_existing=True,
        misfire_grace_time=3600,  # 놓친 작업을 1시간 내에 실행 가능하도록 설정
        coalesce=True,  # 여러 번 놓친 작업을 하나로 합침
    )
    
    scheduler.start()
    logger.info(
        "Scheduler started",
        job_id="daily_amazon_crawl",
        schedule="0 16 * * * (KST)",
        timezone="Asia/Seoul"
    )


def shutdown_scheduler():
    """스케줄러를 종료합니다."""
    scheduler.shutdown()
    logger.info("Scheduler shutdown")
