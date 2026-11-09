@echo off
title Fortune-Cat Bookkeeping

echo ============================================
echo   Fortune-Cat Bookkeeping - One-Click Start
echo ============================================

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
    timeout /t 5 /nobreak >nul
    netstat -ano | find ":8005 " | find "LISTENING" >nul && set BACKEND_OK=1
)
if %BACKEND_OK%==1 (
    echo [OK] Backend is running on port 8005
) else (
    echo [WARN] Backend failed to start. Please check python is installed.
)

rem ---------- 3. Open the page ----------
echo [OK] Opening the page ...
start "" "%~dp0index.html"

echo ============================================
echo   Done! Data is stored in local MySQL, works offline.
echo ============================================
timeout /t 3 >nul
