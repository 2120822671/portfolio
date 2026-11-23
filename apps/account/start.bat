@echo off
title Fortune-Cat Bookkeeping

echo ============================================
echo   Fortune-Cat Bookkeeping - One-Click Start
echo   v2.0 · 多账本 / 看板 / 自动化流程
echo ============================================

rem ---------- 0. 依赖自检 ----------
python -c "import fastapi, uvicorn, pymysql" >nul 2>&1
if errorlevel 1 (
    echo [..] Installing missing dependencies ...
    python -m pip install fastapi uvicorn pymysql apscheduler requests
)
python -c "import apscheduler" >nul 2>&1
if errorlevel 1 (
    echo [..] Installing apscheduler ...
    python -m pip install apscheduler
)

rem ---------- 1. MySQL service ----------
set MYSQL_OK=0
sc query mysql8 | find "RUNNING" >nul && set MYSQL_OK=1
if %MYSQL_OK%==1 (
    echo [OK] MySQL service is running
) else (
    echo [..] Starting MySQL service ...
    net start mysql8 >nul 2>&1
    sc query mysql8 | find "RUNNING" >nul && set MYSQL_OK=1
)
if %MYSQL_OK%==0 (
    echo [WARN] MySQL failed to start. Right-click this bat, "Run as administrator", then try again.
)

rem ---------- 2. Backend on port 8005 ----------
set BACKEND_OK=0
netstat -ano | find ":8005 " | find "LISTENING" >nul && set BACKEND_OK=1
if %BACKEND_OK%==0 (
    echo [..] Starting backend, a minimized window will appear, do NOT close it ...
    start "bookkeeping-backend" /min cmd /c "cd /d %~dp0 && python main.py"
    timeout /t 6 /nobreak >nul
    netstat -ano | find ":8005 " | find "LISTENING" >nul && set BACKEND_OK=1
)
if %BACKEND_OK%==1 (
    echo [OK] Backend is running on port 8005
    echo [OK] Scheduler started: recurring 00:05 / summary 23:00 / review 23:10
) else (
    echo [WARN] Backend failed to start. Please check python is installed.
)

rem ---------- 3. Open the page ----------
rem 用后端托管的同源地址打开，避免 file:// 下的跨域限制
echo [OK] Opening the page ...
start "" "http://localhost:8005/"

echo ============================================
echo   Done! Data is stored in local MySQL, works offline.
echo   Optional: set LLM_API_KEY to enable smart parsing
echo   Tip: if the page looks empty, try http://localhost:8005/
echo ============================================
timeout /t 3 >nul
