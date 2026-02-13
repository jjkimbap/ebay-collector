@echo off
REM FastAPI 서버 백그라운드 실행 스크립트 (Windows)
REM 콘솔 창 없이 백그라운드에서 실행합니다.

echo Starting FastAPI server in background...
start /B python -m uvicorn app.main:app --host 0.0.0.0 
echo Server started in background. Check logs for status.
echo To stop the server, use: taskkill /F /IM python.exe /FI "WINDOWTITLE eq uvicorn*"

pause
