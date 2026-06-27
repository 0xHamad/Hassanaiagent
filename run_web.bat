@echo off
cd /d "%~dp0web"
echo Hassan AI Chat — stopping old server on port 8080...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8080 ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul
echo Starting server...
echo Open: http://127.0.0.1:8080
python -m uvicorn app:app --host 0.0.0.0 --port 8080 --reload
pause
