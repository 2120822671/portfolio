@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title 校淘集市 - 一键启动

set "HOST=127.0.0.1"
set "PORT=8001"
set "BASE=http://%HOST%:%PORT%"

echo.
echo  ============================================
echo    校淘集市 campus_secondhand · 一键启动
echo  ============================================
echo.

rem ---------- 1. 服务是否已在运行 ----------
netstat -ano 2>nul | findstr /C:":%PORT% " | findstr /I "LISTENING" >nul
if not errorlevel 1 (
  echo  [INFO] 服务已在运行，直接打开浏览器...
  start "" "%BASE%/static/index.html"
  goto MENU
)

rem ---------- 2. 检查 Python ----------
where python >nul 2>nul
if errorlevel 1 (
  echo  [ERROR] 未找到 python，请先安装 Python 3.10+ 并加入 PATH
  pause
  exit /b 1
)

rem ---------- 3. 检查依赖 ----------
python -c "import fastapi, sqlalchemy, pymysql, bcrypt, cryptography, apscheduler, aiomysql, loguru" >nul 2>nul
if errorlevel 1 (
  echo  [INFO] 依赖缺失，正在安装 backend\requirements.txt ...
  python -m pip install -r backend\requirements.txt --disable-pip-version-check
  if errorlevel 1 (
    echo  [ERROR] 依赖安装失败，请检查网络或 pip 配置
    pause
    exit /b 1
  )
)

rem ---------- 4. 后台启动服务（日志窗口最小化） ----------
echo  [INFO] 正在启动后端服务（端口 %PORT%）...
pushd "%~dp0backend"
start "校淘集市服务" /MIN cmd /c "python -m uvicorn main:app --host %HOST% --port %PORT%"
popd

rem ---------- 5. 等待就绪（最多 30 秒） ----------
echo  [INFO] 等待服务就绪，请稍候...
set /a N=0
:WAIT
set /a N+=1
timeout /t 1 /nobreak >nul
python -c "import urllib.request;urllib.request.urlopen('http://%HOST%:%PORT%/',timeout=1)" >nul 2>nul
if not errorlevel 1 goto READY
if %N% LSS 30 goto WAIT

echo  [ERROR] 服务启动超时，请查看 minimized 的「校淘集市服务」窗口日志
pause
exit /b 1

:READY
echo  [OK] 服务已就绪，正在打开首页...
start "" "%BASE%/static/index.html"

rem ---------- 6. 快捷入口菜单 ----------
:MENU
echo.
echo  ============================================
echo    常用入口（浏览器已打开首页）
echo  ============================================
echo    [1] 前端首页
echo    [2] 管理看板
echo    [3] 接口文档 Swagger
echo    [4] 发布商品
echo    [5] 查看服务日志窗口
echo    [6] 停止服务
echo    [0] 退出（服务继续在后台运行）
echo.
set "CH="
set /p "CH=  请输入选项后回车: "
if "%CH%"=="1" start "" "%BASE%/static/index.html" & goto MENU
if "%CH%"=="2" start "" "%BASE%/static/admin.html" & goto MENU
if "%CH%"=="3" start "" "%BASE%/docs" & goto MENU
if "%CH%"=="4" start "" "%BASE%/static/publish.html" & goto MENU
if "%CH%"=="5" (
  echo  [INFO] 服务日志在最小化的「校淘集市服务」窗口中，请从任务栏恢复查看。
  timeout /t 2 >nul
  goto MENU
)
if "%CH%"=="6" goto STOP
if "%CH%"=="0" exit /b 0
echo  [WARN] 无效选项，请重新输入
goto MENU

:STOP
echo  [INFO] 正在停止服务...
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /C:":%PORT% " ^| findstr /I "LISTENING"') do (
  taskkill /PID %%P /F >nul 2>nul
)
echo  [OK] 服务已停止
timeout /t 2 >nul
exit /b 0
