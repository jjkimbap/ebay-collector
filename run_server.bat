@echo off
REM FastAPI 서버 실행 스크립트 (Windows)
REM 스케줄러가 포함된 서버를 백그라운드로 실행합니다.

echo Starting FastAPI server with scheduler...
echo Press Ctrl+C to stop the server

python -m uvicorn app.main:app --host 0.0.0.0 


pause
