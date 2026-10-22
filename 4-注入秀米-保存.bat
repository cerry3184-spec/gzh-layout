@echo off
chcp 936 >nul
set PYTHONUTF8=0
set PYTHONIOENCODING=gbk
cd /d "%~dp0"
set PY=C:\Users\weitian\.workbuddy\binaries\python\envs\default\Scripts\python.exe
if not exist "%PY%" set PY=python
"%PY%" -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo [错误] 没找到可用的 Python，请先安装 Python 3.10 以上版本
  echo        下载：https://www.python.org/downloads/
  pause
  exit /b 1
)

echo ==========================================
echo   4. 注入秀米并保存
echo ==========================================
echo.
echo 注意：这会在你的秀米账号里真的创建一篇图文。
echo 建议先用「3-注入秀米-演练.bat」确认排版没问题。
echo.

set /p OK=确认继续？输入 y 回车：
if /i not "%OK%"=="y" goto cancel

echo.
"%PY%" build_gonggao.py --inject --save
echo.
pause
exit /b 0

:cancel
echo.
echo 已取消。
pause
exit /b 0
