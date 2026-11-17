@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting Workload Query web app from source...
echo URL: http://127.0.0.1:5003
echo.
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Run: python -m venv .venv ^&^& pip install -r requirements-mcp.txt
  pause
  exit /b 1
)
".venv\Scripts\python.exe" web_app_inpatient.py
pause
