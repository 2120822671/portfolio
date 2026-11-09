@echo off
chcp 65001 >nul
cd /d %~dp0
rem 3 秒后自动打开浏览器（等后端启动）
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"
echo 正在启动作品集服务（关闭本窗口即停止服务）...
python main.py
pause
