# 스케줄러 실행 가이드

## 📋 개요

이 프로젝트는 **APScheduler**를 사용하여 매일 오전 3시에 자동으로 Amazon 크롤링을 실행합니다.

## 🚀 로컬 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 서버 실행

#### 방법 1: 직접 실행 (권장)

```bash
# 개발 모드 (코드 변경 시 자동 재시작)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload

# 프로덕션 모드 (안정적)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8003
```

#### 방법 2: 배치 파일 사용 (Windows)

```bash
# 일반 실행 (콘솔 창 표시)
run_server.bat

# 백그라운드 실행 (콘솔 창 없음)
run_server_background.bat
```

#### 방법 3: Python 직접 실행

```bash
python -m app.main
```

### 3. 서버 확인

서버가 시작되면 다음 메시지가 표시됩니다:

```
INFO:     Application started
INFO:     Scheduler started job_id="daily_amazon_crawl" schedule="0 3 * * *"
INFO:     Uvicorn running on http://0.0.0.0:8003
```

## ⏰ 스케줄러 설정

### 현재 설정

- **실행 시간**: 매일 오전 3시 (한국 시간 기준)
- **대상**: `price_level=2`인 모든 고객
- **수집 개수**: 각 키워드당 5개 상품 (기본값)

### 설정 변경

`app/core/scheduler.py` 파일에서 설정을 변경할 수 있습니다:

```python
async def scheduled_crawl_amazon():
    price_level = 2      # 가격 레벨 변경
    limit = 5            # 키워드당 수집 개수 변경
```

### 실행 시간 변경

`app/core/scheduler.py`의 `setup_scheduler()` 함수에서 변경:

```python
# 매일 오전 3시
scheduler.add_job(
    scheduled_crawl_amazon,
    trigger=CronTrigger(hour=3, minute=0),  # hour, minute 변경
    ...
)
```

**예시:**
- `hour=9, minute=30` → 매일 오전 9시 30분
- `hour=0, minute=0` → 매일 자정
- `hour=14, minute=0` → 매일 오후 2시

## 🔍 스케줄러 동작 확인

### 로그 확인

스케줄러가 실행되면 다음과 같은 로그가 출력됩니다:

```
INFO: Scheduled crawl started price_level=2 limit=5
INFO: Scheduled crawl - customers retrieved price_level=2 customer_count=3
INFO: Scheduled crawl completed successfully total_customers=3 processed_customers=3 total_items=45 saved_items=45
```

### 수동 실행 (테스트용)

스케줄러를 기다리지 않고 바로 테스트하려면:

```bash
# 단일 고객 크롤링
curl "http://localhost:8003/api/crawl/amazon?customer_cd=2&price_level=2&limit=5"

# 배치 크롤링 (모든 고객)
curl "http://localhost:8003/api/crawl/amazon/batch?price_level=2&limit=5"
```

## ⚠️ 주의사항

### 1. 서버가 계속 실행되어야 함

스케줄러는 서버가 실행 중일 때만 동작합니다. 서버를 종료하면 스케줄러도 중지됩니다.

### 2. Windows 백그라운드 실행

Windows에서 백그라운드로 실행하려면:
- 작업 스케줄러 사용
- 서비스로 등록
- 또는 `run_server_background.bat` 사용

### 3. 서버 재시작 시

서버를 재시작하면 스케줄러도 자동으로 재시작됩니다. 다음 실행 시간까지 대기합니다.

### 4. 타임존 주의

스케줄러는 서버의 시스템 타임존을 사용합니다. 한국 시간으로 실행하려면 서버의 타임존이 KST로 설정되어 있어야 합니다.

## 🛠️ 문제 해결

### 스케줄러가 실행되지 않는 경우

1. **서버 로그 확인**: `Scheduler started` 메시지가 있는지 확인
2. **의존성 확인**: `apscheduler`가 설치되어 있는지 확인
   ```bash
   pip list | findstr apscheduler
   ```
3. **수동 실행 테스트**: API를 직접 호출하여 크롤링이 동작하는지 확인

### 서버가 종료되는 경우

1. **에러 로그 확인**: 콘솔에 표시되는 에러 메시지 확인
2. **포트 충돌 확인**: 다른 프로세스가 8003 포트를 사용 중인지 확인
   ```bash
   netstat -ano | findstr :8003
   ```
3. **의존성 확인**: MongoDB 연결 등 필수 서비스가 실행 중인지 확인

## 📝 추가 정보

- 스케줄러 설정: `app/core/scheduler.py`
- 크롤링 로직: `app/services/crawl_service.py`
- API 엔드포인트: `app/api/crawl_amazon.py`
