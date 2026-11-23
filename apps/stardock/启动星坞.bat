@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title ⭐ 星坞 StarDock 启动器

REM ============================================
REM  星坞 StarDock 一键启动
REM  1. 检查 8000 端口 → 已有服务就跳过启动
REM  2. 没有则启动 FastAPI 后端（后台运行）
REM  3. 等后端就绪 → 自动打开浏览器
REM ============================================

set "PROJ_DIR=%~dp0"
set "BACKEND=%PROJ_DIR%backend"
set "PYTHON=C:\Users\21208\AppData\Local\Programs\Python\Python314\python.exe"
set "URL=http://localhost:8000/login.html"

echo.
echo    ╔══════════════════════════════╗
echo    ║     ⭐  星坞 StarDock  ⭐     ║
echo    ║        一键启动器 v1.0        ║
echo    ╚══════════════════════════════╝
echo.

REM ---- 步骤 1: 检查端口 8000 ----
echo [1/3] 检查后端服务...
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo       ✅ 后端已在运行，跳过启动
    goto :open_browser
)

REM ---- 步骤 2: 启动后端 ----
echo [2/3] 启动 FastAPI 后端服务...
if not exist "%PYTHON%" (
    echo       ❌ Python 未找到: %PYTHON%
    echo       请检查路径或修改此脚本第 11 行的 PYTHON 变量
    pause
    exit /b 1
)

if not exist "%BACKEND%\main.py" (
    echo       ❌ 后端入口未找到: %BACKEND%\main.py
    pause
    exit /b 1
)

cd /d "%BACKEND%"
start "星坞后端" /min "%PYTHON%" main.py

REM ---- 步骤 3: 等待后端就绪（最多 15 秒）----
echo [3/3] 等待后端就绪...
set "READY=0"
for /L %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8000/api/health 2>nul | findstr "200" >nul 2>&1
    if !errorlevel!==0 (
        set "READY=1"
        echo       ✅ 后端已就绪 ^(耗时 %%i 秒^)
        goto :open_browser
    )
    echo       ... 等待中 %%i/15
)

echo       ⚠️  等待超时，后端可能还在启动，继续打开浏览器
goto :open_browser

:open_browser
echo.
echo    🚀 正在打开浏览器...
start "" "%URL%"
echo.
echo    ✅ 搞定！浏览器应该已经弹出。
echo    如果页面空白，稍等几秒刷新一下。
echo.
echo    💡 后端在后台运行，关闭此窗口不会停服务。
echo       要停服务：打开任务管理器 → 结束 python.exe
echo.
pause
